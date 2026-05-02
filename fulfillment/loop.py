"""
Auto-fulfillment loop.

Run:  python -m fulfillment.loop

Every 15 minutes:
  1. Fetch new paid+unfulfilled Shopify orders
  2. Resolve each line item → CJ variant ID via arbitrage.supplier_url metafield
  3. Place CJ order with customer shipping address
  4. Check pending CJ orders for tracking → push to Shopify when shipped
"""
import time

from fulfillment.order_monitor import (
    get_new_orders,
    get_product_metafields,
    mark_fulfilled,
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
        for item in order.get("line_items", []):
            pid_shopify = item.get("product_id")
            if not pid_shopify:
                print(f"    Skipping line item '{item.get('title')}' — no product_id")
                continue

            meta = get_product_metafields(pid_shopify)
            supplier_url = meta.get("arbitrage.supplier_url", "")
            cj_pid = _cj_pid_from_url(supplier_url)

            if not cj_pid:
                print(f"    '{item.get('title')}' — no CJ pid in metafields, skipping")
                continue

            variants = get_cj_variants(cj_pid)
            if not variants:
                print(f"    '{item.get('title')}' — CJ variants not found for pid {cj_pid}")
                continue

            vid = variants[0].get("vid") or variants[0].get("variantId", "")
            country = (order.get("shipping_address") or {}).get("country_code", "US")
            shipping = get_cheapest_shipping(vid, country)

            cj_items.append({
                "vid": vid,
                "quantity": item.get("quantity", 1),
                "shipping_name": shipping,
            })
            print(f"    + '{item.get('title')}' → CJ vid={vid}, ship={shipping}")

        if not cj_items:
            print(f"  No fulfillable items in {name} — skipping")
            continue

        try:
            cj_order_id = place_cj_order(order, cj_items)
            mark_fulfilled(order["id"], cj_order_id)
            print(f"  CJ order created: {cj_order_id}")
        except Exception as exc:
            print(f"  FAILED to place CJ order for {name}: {exc}")


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
                print(f"    Failed to push tracking to Shopify: {exc}")
        else:
            print(f"    CJ {cj_id}: not yet shipped")


def main():
    print("Auto-fulfillment loop running. Ctrl+C to stop.\n")
    while True:
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
        print(f"\n  Sleeping {POLL_INTERVAL // 60} min until next poll.")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
