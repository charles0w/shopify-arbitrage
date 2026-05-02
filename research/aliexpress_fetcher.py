"""
Fetch product listings from AliExpress via RapidAPI aliexpress-datahub.
Requires RAPIDAPI_KEY in .env.

Each returned product dict has:
  id, title, supplier_price_usd, shipping_weight_lbs,
  review_count, orders_count, image_urls, product_url
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

_RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
_SEARCH_URL = "https://aliexpress-datahub.p.rapidapi.com/item_search_2"
_DETAIL_URL = "https://aliexpress-datahub.p.rapidapi.com/item_detail_2"
_HEADERS = {
    "X-RapidAPI-Key": _RAPIDAPI_KEY,
    "X-RapidAPI-Host": "aliexpress-datahub.p.rapidapi.com",
}


def search_products(keyword: str, max_results: int = 20) -> list[dict]:
    """Search AliExpress for keyword. Returns up to max_results products."""
    if not _RAPIDAPI_KEY:
        raise EnvironmentError("RAPIDAPI_KEY not set in .env")

    params = {"keywords": keyword, "page": "1", "sort": "SALE_PRICE_ASC"}
    resp = requests.get(_SEARCH_URL, headers=_HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("result", {}).get("resultList", []) or []
    products = []
    for item in items[:max_results]:
        info = item.get("item", {})
        prices = info.get("sku", {}).get("def", {})
        price_str = prices.get("promotionPrice") or prices.get("price") or "0"
        try:
            price = float(str(price_str).replace("US $", "").replace(",", "").strip())
        except ValueError:
            price = 0.0

        products.append({
            "id": str(info.get("itemId", "")),
            "title": info.get("title", ""),
            "supplier_price_usd": price,
            "shipping_weight_lbs": None,  # enriched in get_product_detail
            "review_count": int(info.get("averageStarRate", 0) or 0),
            "orders_count": _parse_orders(info.get("tradeDesc", "")),
            "image_urls": [info.get("image", "")],
            "product_url": f"https://www.aliexpress.com/item/{info.get('itemId')}.html",
        })

    return products


def get_product_detail(product_id: str) -> dict:
    """Fetch full detail for a single product — adds shipping weight and more images."""
    params = {"itemId": product_id, "currency": "USD", "locale": "en_US"}
    resp = requests.get(_DETAIL_URL, headers=_HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("result", {})

    images = data.get("imagePathList", [])
    weight_g = None
    props = data.get("productPropComponent", {}).get("propList", [])
    for prop in props:
        if "weight" in prop.get("attrName", "").lower():
            try:
                weight_g = float(prop.get("attrValue", "").replace("g", "").strip())
            except ValueError:
                pass

    return {
        "image_urls": images,
        "shipping_weight_lbs": round(weight_g / 453.6, 2) if weight_g else None,
        "description_html": data.get("description", ""),
    }


def _parse_orders(trade_desc: str) -> int:
    """Parse '1.2k+ sold' → 1200."""
    if not trade_desc:
        return 0
    s = trade_desc.lower().replace("sold", "").replace("+", "").strip()
    try:
        if "k" in s:
            return int(float(s.replace("k", "")) * 1000)
        return int(s)
    except ValueError:
        return 0
