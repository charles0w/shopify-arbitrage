"""
Weekly repricing run.

Fetches all active Shopify products, reads stored supplier price from metafields,
and reapplies the markup formula. Only updates if price changed by > 5%.

Run: python -m pipeline.weekly_reprice
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from listing.shopify_publisher import list_active_products, update_price
from config.settings import MARKUP, DEFAULT_MARKUP


def _markup_for(cost: float) -> float:
    for threshold in sorted(MARKUP):
        if cost < threshold:
            return MARKUP[threshold]
    return DEFAULT_MARKUP


def run():
    print("[weekly_reprice] Fetching active products...")
    products = list_active_products()
    updated = 0

    for product in products:
        supplier_price = None
        for mf in product.get("metafields", []):
            if mf.get("namespace") == "arbitrage" and mf.get("key") == "supplier_price":
                try:
                    supplier_price = float(mf["value"])
                except ValueError:
                    pass

        if supplier_price is None:
            continue

        markup = _markup_for(supplier_price)
        new_price = round(supplier_price * markup, 2)

        for variant in product.get("variants", []):
            try:
                current_price = float(variant.get("price", 0))
            except ValueError:
                continue
            if current_price == 0:
                continue

            change_pct = abs(new_price - current_price) / current_price
            if change_pct > 0.05:
                print(f"  Repricing '{product['title'][:50]}': "
                      f"${current_price:.2f} → ${new_price:.2f}")
                update_price(product["id"], variant["id"], new_price)
                updated += 1

    print(f"[weekly_reprice] Done. {updated} variant(s) updated.")


if __name__ == "__main__":
    run()
