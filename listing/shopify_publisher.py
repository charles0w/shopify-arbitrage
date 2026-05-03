"""
Publish a product listing to Shopify as a DRAFT via the Admin REST API.
Uploads images, sets price, and returns the Shopify product ID.
"""
import base64
import os
import requests
from pathlib import Path
from config.settings import SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN

_BASE = f"https://{SHOPIFY_STORE_URL}/admin/api/2024-01"
_HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json",
}


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def create_draft(listing: dict, product: dict, image_paths: list[str]) -> dict:
    """
    Create a draft Shopify product and return the API response dict.

    listing: output of listing_generator.generate_listing()
    product: scored product dict (has supplier_price, suggested_sale_price, etc.)
    image_paths: local file paths from image_processor.download_images()
    """
    images = [
        {"attachment": _encode_image(p), "position": i + 1}
        for i, p in enumerate(image_paths)
        if Path(p).exists()
    ]

    payload = {
        "product": {
            "title": listing["title"],
            "body_html": listing["body_html"],
            "tags": ", ".join(listing.get("tags", [])),
            "status": "draft",
            "variants": [
                {
                    "price": str(product["suggested_sale_price_usd"]),
                    "requires_shipping": True,
                    "taxable": True,
                    "inventory_management": None,  # no inventory tracking for dropship
                }
            ],
            "images": images,
            "metafields": [
                {
                    "namespace": "seo",
                    "key": "title",
                    "value": listing.get("meta_title", listing["title"]),
                    "type": "single_line_text_field",
                },
                {
                    "namespace": "seo",
                    "key": "description",
                    "value": listing.get("meta_description", ""),
                    "type": "single_line_text_field",
                },
                {
                    "namespace": "arbitrage",
                    "key": "supplier_url",
                    "value": product.get("product_url", ""),
                    "type": "url",
                },
                {
                    "namespace": "arbitrage",
                    "key": "supplier_price",
                    "value": str(product.get("supplier_price_usd", 0)),
                    "type": "single_line_text_field",
                },
            ],
        }
    }

    resp = requests.post(f"{_BASE}/products.json", json=payload, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["product"]


def list_active_products() -> list[dict]:
    """Return all active (published) products from Shopify."""
    products = []
    url = f"{_BASE}/products.json?status=active&limit=250"
    while url:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        products.extend(resp.json().get("products", []))
        link = resp.headers.get("Link", "")
        url = _next_page_url(link)
    return products


def update_price(product_id: int, variant_id: int, new_price: float):
    url = f"{_BASE}/variants/{variant_id}.json"
    resp = requests.put(url, json={"variant": {"price": str(new_price)}}, headers=_HEADERS, timeout=15)
    resp.raise_for_status()


def get_product_metafields(product_id: int) -> dict:
    """Return {"namespace.key": value} for all metafields on a Shopify product.

    list_active_products / GET /products.json doesn't return metafields, so
    weekly_reprice has to fetch them per product to find the stored
    arbitrage.supplier_price.
    """
    resp = requests.get(
        f"{_BASE}/products/{product_id}/metafields.json",
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return {
        f"{mf['namespace']}.{mf['key']}": mf["value"]
        for mf in resp.json().get("metafields", [])
    }


def _next_page_url(link_header: str) -> str | None:
    for part in link_header.split(","):
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return None
