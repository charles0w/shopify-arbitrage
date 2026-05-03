"""
Auto-fulfillment loop.

Run continuously:    python -m fulfillment.loop
Run a single tick:   python -m fulfillment.loop --once

Each tick:
  1. Fetch new paid+unfulfilled Shopify orders
  2. Resolve each line item → CJ variant ID via arbitrage.supplier_url metafield
  3. Place CJ order with customer shipping address
  4. Check pending CJ orders for tracking → push to Shopify when shipped

Use --once for cron-style scheduling (e.g. GitHub Actions every 15 min).
"""
import os
import sys
import time

import requests

from fulfillment.order_monitor import (
    get_new_orders,
    get_product_metafields,
    mark_fulfilled,
    mark_error,
    mark_tracking_failed,
    get_pending_tracking,
    drop_tracking_entry,
    push_tracking_to_shopify,
)
from fulfillment.cj_fulfiller import (
    get_cj_variants,
    get_cheapest_shipping,
    place_cj_order,
    get_order_tracking,
)

POLL_INTERVAL = 900  # 15 minutes


def _alert(message: str):
    """Post an error alert to DIGEST_WEBHOOK_URL if configured.
    Same {"text": "..."} payload shape as the daily research digest —
    Slack/Discord-compatible."""
    url = os.environ.get("DIGEST_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(url, json={"text": message}, timeout=10)
    except Exception as exc:
        print(f"  Alert webhook failed: {exc}")


def _cj_pid_from_url(supplier_url: str) -> str | None:
    """Extract CJ pid from 'https://cjdropshipping.com/product/-p-{pid}.html'."""
    try:
        return supplier_url.split("-p-")[1].replace(".html", "").strip()
    except (IndexError, AttributeError):
        return None


def fulfill_new_orders():
    orders = get_new_orders()
    if not orders:
        print("  No new orders.")
        return

    for order in orders:
        name = order.get("name", order["id"])
        print(f"\n  Order {name}  (id={order['id']})")

        cj_items = []
        skip_reasons = []
        for item in order.get("line_items", []):
            title = item.get("title", "?")
            pid_shopify = item.get("product_id")
            if not pid_shopify:
                reason = f"'{title}' has no product_id"
                print(f"    Skipping line item — {reason}")
                skip_reasons.append(reason)
                continue

            meta = get_product_metafields(pid_shopify)
            supplier_url = meta.get("arbitrage.supplier_url", "")
            cj_pid = _cj_pid_from_url(supplier_url)

            if not cj_pid:
                reason = f"'{title}' missing arbitrage.supplier_url metafield"
                print(f"    {reason}, skipping")
                skip_reasons.append(reason)
                continue

            variants = get_cj_variants(cj_pid)
            if not variants:
                reason = f"'{title}' — no CJ variants for pid {cj_pid}"
                print(f"    {reason}")
                skip_reasons.append(reason)
                continue

            vid = variants[0].get("vid") or variants[0].get("variantId", "")
            country = (order.get("shipping_address") or {}).get("country_code", "US")
            try:
                shipping = get_cheapest_shipping(vid, country)
            except Exception as exc:
                reason = f"'{title}' — shipping calc failed: {exc}"
                print(f"    {reason}")
                skip_reasons.append(reason)
                continue

            cj_items.append({
                "vid": vid,
                "quantity": item.get("quantity", 1),
                "shipping_name": shipping,
            })
            print(f"    + '{title}' → CJ vid={vid}, ship={shipping}")

        if not cj_items:
            reason = "no eligible line items: " + "; ".join(skip_reasons) if skip_reasons else "no line items on order"
            print(f"  {name} — {reason}")
            mark_error(order["id"], reason, order=order)
            _alert(f":warning: {name}: {reason}")
            continue

        try:
            cj_order_id = place_cj_order(order, cj_items)
            mark_fulfilled(order["id"], cj_order_id, order=order)
            print(f"  CJ order created: {cj_order_id}")
        except Exception as exc:
            print(f"  FAILED to place CJ order for {name}: {exc}")
            mark_error(order["id"], str(exc), order=order)
            _alert(f":warning: CJ order failed for Shopify {name}: {exc}")


def check_tracking():
    pending = get_pending_tracking()
    if not pending:
        return

    print(f"\n  Checking tracking for {len(pending)} CJ order(s)...")
    for entry in pending:
        cj_id = entry["cj_order_id"]
        shopify_id = entry["shopify_order_id"]

        try:
            tracking = get_order_tracking(cj_id)
        except Exception as exc:
            print(f"    CJ {cj_id}: error checking status — {exc}")
            continue

        if tracking:
            number = tracking["tracking_number"]
            carrier = tracking["carrier"]
            print(f"    CJ {cj_id} shipped: {number} via {carrier}")
            try:
                push_tracking_to_shopify(shopify_id, number, carrier)
                drop_tracking_entry(cj_id)
                print(f"    Tracking pushed to Shopify order {shopify_id} ✓")
            except Exception as exc:
                msg = f"tracking push failed: {exc}"
                print(f"    Failed to push tracking to Shopify: {exc}")
                # Pending tracking entry stays in place — next tick will retry
                # the push automatically. Surface to the dashboard, and alert
                # only on the first failure (or when the message changes).
                if mark_tracking_failed(shopify_id, msg):
                    _alert(
                        f":warning: Shopify {shopify_id}: tracking push failed "
                        f"(CJ {cj_id} is shipped, customer hasn't been notified): {exc}"
                    )
        else:
            print(f"    CJ {cj_id}: not yet shipped")


def run_once():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Polling...")
    try:
        fulfill_new_orders()
    except Exception as exc:
        print(f"  Error in order fulfillment: {exc}")
    try:
        check_tracking()
    except Exception as exc:
        print(f"  Error in tracking check: {exc}")


def main():
    print("Auto-fulfillment loop running. Ctrl+C to stop.\n")
    while True:
        run_once()
        print(f"\n  Sleeping {POLL_INTERVAL // 60} min until next poll.")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        main()
