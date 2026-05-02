"""
Green-light approval CLI.

Usage:
  python -m pipeline.approve                  # approve today's queue interactively
  python -m pipeline.approve 2026-05-01       # approve specific date interactively
  python -m pipeline.approve 2026-05-01 0 2 4 # approve products at indices 0, 2, 4 directly

For each approved product:
  1. Downloads supplier images
  2. Generates listing copy with Claude API
  3. Creates a DRAFT product on Shopify
  4. Prints the Shopify admin URL
"""
import json
import sys
import os
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth.shopify_token import get_token
from listing.listing_generator import generate_listing
from listing.image_processor import download_images
from listing.shopify_publisher import create_draft
from config.settings import SHOPIFY_STORE_URL

QUEUE_DIR = Path(__file__).parent.parent / "queue"


def _load_queue(queue_date: str) -> list[dict]:
    path = QUEUE_DIR / f"{queue_date}.json"
    if not path.exists():
        raise FileNotFoundError(f"No queue file found for {queue_date}. Run daily_research first.")
    with open(path) as f:
        return json.load(f)


def _print_queue(products: list[dict]):
    for i, p in enumerate(products):
        print(f"  [{i}] score={p['score']} ${p.get('supplier_price_usd',0):.2f}→"
              f"${p.get('suggested_sale_price_usd',0):.2f}  {p['title'][:60]}")


def _process(product: dict):
    print(f"  → Downloading images...")
    images = download_images(product.get("image_urls", []), max_images=5)

    print(f"  → Generating listing copy with Claude...")
    listing = generate_listing(product)
    print(f"     Title: {listing['title']}")

    print(f"  → Publishing draft to Shopify...")
    shopify_product = create_draft(listing, product, images)
    pid = shopify_product["id"]
    print(f"     Draft live: https://{SHOPIFY_STORE_URL}/admin/products/{pid}")
    return shopify_product


def run(queue_date: str, indices: list[int] | None = None):
    get_token()
    products = _load_queue(queue_date)

    if indices is None:
        print(f"\nQueue for {queue_date} ({len(products)} products):")
        _print_queue(products)
        raw = input("\nEnter indices to approve (space-separated, or 'all'): ").strip()
        if raw.lower() == "all":
            indices = list(range(len(products)))
        else:
            indices = [int(x) for x in raw.split() if x.isdigit()]

    print(f"\nApproving {len(indices)} product(s)...")
    for i in indices:
        if i >= len(products):
            print(f"  [!] Index {i} out of range — skipping")
            continue
        p = products[i]
        print(f"\n[{i}] {p['title'][:70]}")
        try:
            _process(p)
        except Exception as e:
            print(f"  [!] Failed: {e}")

    print("\nDone.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        q_date = date.today().isoformat()
        run(q_date)
    elif len(args) == 1:
        run(args[0])
    else:
        run(args[0], [int(x) for x in args[1:]])
