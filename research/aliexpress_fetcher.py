"""
Fetch product listings from CJDropshipping API.
US warehouse products = 5-7 day delivery to US customers.

Requires in .env:
  CJ_EMAIL
  CJ_PASSWORD

Docs: https://developers.cjdropshipping.com/
"""
import os
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_API_KEY = os.environ.get("CJ_API_KEY", "")
_BASE = "https://developers.cjdropshipping.com/api2.0/v1"
_CACHE = Path(__file__).parent.parent / ".cj_token_cache.json"


def _get_token() -> str:
    """Return a valid CJ access token, refreshing if expired."""
    if _CACHE.exists():
        with open(_CACHE) as f:
            cached = json.load(f)
        if time.time() < cached.get("expires_at", 0) - 300:
            return cached["accessToken"]

    if not _API_KEY:
        raise EnvironmentError("CJ_API_KEY not set in .env")

    resp = requests.post(
        f"{_BASE}/authentication/getAccessToken",
        json={"apiKey": _API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("result"):
        raise RuntimeError(f"CJ auth failed: {data.get('message')}")

    token_data = data["data"]
    token_data["expires_at"] = time.time() + 86400 * 14  # tokens valid ~2 weeks
    with open(_CACHE, "w") as f:
        json.dump(token_data, f)

    return token_data["accessToken"]


def _headers() -> dict:
    return {"CJ-Access-Token": _get_token()}


def search_products(keyword: str, max_results: int = 20) -> list[dict]:
    """Search CJDropshipping products by keyword."""
    resp = requests.get(
        f"{_BASE}/product/list",
        headers=_headers(),
        params={
            "productName": keyword,
            "pageNum": 1,
            "pageSize": min(max_results, 50),
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("result"):
        print(f"  [CJ] no results for '{keyword}': {data.get('message')}")
        return []

    items = data.get("data", {}).get("list", []) or []
    return [_parse_product(p, keyword) for p in items[:max_results]]


def get_product_detail(product_id: str) -> dict:
    """Fetch full detail for a single CJ product."""
    resp = requests.get(
        f"{_BASE}/product/query",
        headers=_headers(),
        params={"pid": product_id},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("result"):
        return {}

    p = data.get("data", {})
    images = [v.get("imageUrl", "") for v in p.get("productImageSet", []) if v.get("imageUrl")]
    weight_g = None
    for variant in p.get("variants", []):
        if variant.get("variantWeight"):
            try:
                weight_g = float(variant["variantWeight"])
                break
            except ValueError:
                pass

    return {
        "image_urls": images,
        "shipping_weight_lbs": round(weight_g / 453.6, 2) if weight_g else None,
        "description_html": p.get("description", ""),
    }


def _parse_product(p: dict, keyword: str) -> dict:
    # sellPrice can be "3.27 -- 4.42" or "5.00" — take the low end
    raw_price = str(p.get("sellPrice") or "0").split("--")[0].strip()
    try:
        price = float(raw_price)
    except ValueError:
        price = 0.0

    # productWeight is grams, may be range like "20-38" — take low end
    raw_weight = str(p.get("productWeight") or "0").split("-")[0].strip()
    try:
        weight_lbs = round(float(raw_weight) / 453.6, 2) if float(raw_weight) > 0 else None
    except ValueError:
        weight_lbs = None

    image = p.get("productImage", "")

    return {
        "id": str(p.get("pid") or p.get("productId") or ""),
        "title": p.get("productNameEn") or p.get("productName") or "",
        "supplier_price_usd": price,
        "shipping_weight_lbs": weight_lbs,
        "review_count": 0.0,
        "orders_count": int(p.get("quantitySold") or 0),
        "image_urls": [image] if image else [],
        "product_url": f"https://cjdropshipping.com/product/-p-{p.get('pid')}.html",
        "keyword": keyword,
    }
