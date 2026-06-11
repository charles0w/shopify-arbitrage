"""
Weekly repricing run.

Fetches all active Shopify products, reads stored supplier price from
metafields, and reapplies the markup formula. Only updates if the price
changed by > 5%.

Run: python -m pipeline.weekly_reprice
"""
import os
import sys
import time
import traceback

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import ceo_report

try:
    from listing.shopify_publisher import (
        list_active_products,
        update_price,
        get_product_metafields,
    )
    from config.settings import MARKUP, DEFAULT_MARKUP
except Exception as _startup_err:
    ceo_report.report(
        "error",
        f"startup failed: {type(_startup_err).__name__}: {str(_startup_err).splitlines()[0][:120]}",
        ok=False,
    )
    raise

_RETRY_BACKOFF_S = (1, 3, 8)


def _markup_for(cost: float) -> float:
    for threshold in sorted(MARKUP):
        if cost < threshold:
            return MARKUP[threshold]
    return DEFAULT_MARKUP


def _post_webhook(text: str):
    """Slack/Discord-compatible alert. Same shape as daily_research's poster
    so all pipeline alerts land in the same channel."""
    url = os.environ.get("DIGEST_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(url, json={"text": text}, timeout=10)
    except Exception as e:
        print(f"[weekly_reprice] Webhook post failed: {e}")


def _update_price_with_retry(product_id: int, variant_id: int, new_price: float):
    """Retry update_price on transient Shopify failure. Caller catches per
    variant so one bad PUT doesn't abort the whole repricing run."""
    last_exc: Exception | None = None
    for attempt in range(len(_RETRY_BACKOFF_S) + 1):
        try:
            return update_price(product_id, variant_id, new_price)
        except Exception as exc:
            last_exc = exc
            if attempt < len(_RETRY_BACKOFF_S):
                print(f"  update_price retry {attempt + 1} after error: {exc}")
                time.sleep(_RETRY_BACKOFF_S[attempt])
    assert last_exc is not None
    raise last_exc


def run():
    started = time.monotonic()
    try:
        result = _run()
    except Exception as exc:
        tb = traceback.format_exc()
        summary = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
        _post_webhook(
            f":rotating_light: Weekly reprice FAILED\n"
            f"{type(exc).__name__}: {summary}\n"
            f"```\n{tb[-1500:]}\n```"
        )
        ceo_report.report(
            "error",
            f"weekly reprice failed: {type(exc).__name__}: {summary[:120]}",
            ok=False,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise
    ceo_report.report(
        "ok",
        f"reprice — {result['updated']} repriced, {result['failed']} failed, "
        f"{result['skipped']} skipped",
        duration_ms=int((time.monotonic() - started) * 1000),
        metrics=[
            {"label": "Repriced", "value": result["updated"]},
            {"label": "Failed", "value": result["failed"]},
            {"label": "Skipped", "value": result["skipped"]},
        ],
    )
    return result


def _run():
    print("[weekly_reprice] Fetching active products...")
    products = list_active_products()
    print(f"[weekly_reprice] {len(products)} active products to inspect")

    updated = 0
    failed = 0
    skipped_no_metafield = 0

    for product in products:
        # GET /products.json doesn't include metafields — fetch per-product.
        try:
            mf = get_product_metafields(product["id"])
        except Exception as exc:
            print(f"  [{product['id']}] metafield fetch failed: {exc} — skipping")
            failed += 1
            continue

        raw = mf.get("arbitrage.supplier_price")
        if raw is None:
            skipped_no_metafield += 1
            continue
        try:
            supplier_price = float(raw)
        except (TypeError, ValueError):
            print(f"  [{product['id']}] non-numeric supplier_price: {raw!r} — skipping")
            failed += 1
            continue

        markup = _markup_for(supplier_price)
        new_price = round(supplier_price * markup, 2)

        for variant in product.get("variants", []):
            try:
                current_price = float(variant.get("price", 0))
            except (TypeError, ValueError):
                continue
            if current_price == 0:
                continue

            change_pct = abs(new_price - current_price) / current_price
            if change_pct <= 0.05:
                continue

            print(f"  Repricing '{product['title'][:50]}': "
                  f"${current_price:.2f} → ${new_price:.2f}")
            try:
                _update_price_with_retry(product["id"], variant["id"], new_price)
                updated += 1
            except Exception as exc:
                print(f"    update_price gave up: {exc}")
                failed += 1

    print(f"[weekly_reprice] Done. updated={updated} failed={failed} "
          f"no_supplier_metafield={skipped_no_metafield}")

    if updated or failed:
        _post_webhook(
            f"*Weekly reprice* — {updated} variant(s) repriced"
            + (f", {failed} failure(s)" if failed else "")
            + (f", {skipped_no_metafield} skipped (no supplier_price metafield)"
               if skipped_no_metafield else "")
        )

    return {"updated": updated, "failed": failed, "skipped": skipped_no_metafield}


if __name__ == "__main__":
    run()
