"""
End-to-end listing test using hardcoded mock products.
Tests: Claude copy generation → image download → Shopify draft creation.

Run: python -m pipeline.test_listing
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from listing.listing_generator import generate_listing
from listing.image_processor import download_images
from listing.shopify_publisher import create_draft
from config.settings import SHOPIFY_STORE_URL

MOCK_PRODUCTS = [
    {
        "id": "mock-001",
        "title": "Pet Hair Remover Glove - Reusable Grooming Mitt for Dogs & Cats",
        "keyword": "pet accessories",
        "supplier_price_usd": 2.99,
        "suggested_sale_price_usd": 11.99,
        "markup": 4.0,
        "score": 0.78,
        "orders_count": 6800,
        "review_count": 4.8,
        "shipping_weight_lbs": 0.3,
        "product_url": "https://www.aliexpress.com/item/3256809174932303.html",
        "image_urls": [
            "https://ae-pic-a1.aliexpress-media.com/kf/S1fe3419078694d32ad5f2d048ff26e8cN.png"
        ],
    },
    {
        "id": "mock-002",
        "title": "Adjustable Desk Cable Management Organizer Clip Set - 10 Pack",
        "keyword": "home organization",
        "supplier_price_usd": 1.49,
        "suggested_sale_price_usd": 5.99,
        "markup": 4.0,
        "score": 0.72,
        "orders_count": 12400,
        "review_count": 4.7,
        "shipping_weight_lbs": 0.2,
        "product_url": "https://www.aliexpress.com/item/3256801234567890.html",
        "image_urls": [
            "https://ae-pic-a1.aliexpress-media.com/kf/HTB1qg3OXIfrK1RjSspbq6A4pFXak.jpg"
        ],
    },
    {
        "id": "mock-003",
        "title": "Resistance Band Set with Door Anchor - 5 Levels Home Gym Workout",
        "keyword": "fitness accessories",
        "supplier_price_usd": 4.20,
        "suggested_sale_price_usd": 16.80,
        "markup": 4.0,
        "score": 0.75,
        "orders_count": 9100,
        "review_count": 4.6,
        "shipping_weight_lbs": 0.8,
        "product_url": "https://www.aliexpress.com/item/3256809876543210.html",
        "image_urls": [
            "https://ae-pic-a1.aliexpress-media.com/kf/HTB1resistance.jpg"
        ],
    },
]


def run():
    print(f"\n{'='*60}")
    print(f"  END-TO-END LISTING TEST — {len(MOCK_PRODUCTS)} products")
    print(f"  Store: {SHOPIFY_STORE_URL}")
    print(f"{'='*60}\n")

    results = []
    for i, product in enumerate(MOCK_PRODUCTS):
        print(f"[{i+1}/{len(MOCK_PRODUCTS)}] {product['title'][:55]}...")

        # Step 1: Generate listing copy with Claude
        print("  → Generating copy with Claude...")
        try:
            listing = generate_listing(product)
            print(f"     Title: {listing['title']}")
            print(f"     Tags:  {', '.join(listing.get('tags', [])[:4])}")
        except Exception as e:
            print(f"  [!] Claude failed: {e}")
            continue

        # Step 2: Download images
        print("  → Downloading images...")
        images = download_images(product["image_urls"], max_images=3)
        print(f"     {len(images)} image(s) saved")

        # Step 3: Publish draft to Shopify
        print("  → Creating Shopify draft...")
        try:
            shopify_product = create_draft(listing, product, images)
            pid = shopify_product["id"]
            url = f"https://{SHOPIFY_STORE_URL}/admin/products/{pid}"
            print(f"     DRAFT LIVE: {url}")
            results.append({"product": product["title"], "shopify_id": pid, "url": url})
        except Exception as e:
            print(f"  [!] Shopify failed: {e}")
            # Still show the listing copy so we know Claude worked
            print(f"\n  --- Generated listing (Shopify skipped) ---")
            print(f"  Title: {listing['title']}")
            print(f"  Body:  {listing.get('body_html','')[:200]}")
            print()
            continue

        print()

    print(f"{'='*60}")
    print(f"  DONE — {len(results)}/{len(MOCK_PRODUCTS)} drafts created on Shopify")
    for r in results:
        print(f"  • {r['product'][:45]} → {r['url']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()
