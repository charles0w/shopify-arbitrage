"""
Fetch product listings from AliExpress via the official Affiliate Open Platform API.
Docs: https://developers.aliexpress.com/

Requires in .env:
  ALIEXPRESS_APP_KEY
  ALIEXPRESS_APP_SECRET

Each returned product dict has:
  id, title, supplier_price_usd, shipping_weight_lbs,
  review_count, orders_count, image_urls, product_url
"""
import os
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

load_dotenv()

_APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "")
_APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "")
_BASE_URL = "https://api-sg.aliexpress.com/sync"


def _sign(params: dict) -> str:
    """Generate HMAC-SHA256 signature required by AliExpress Open API."""
    sorted_params = sorted(params.items())
    sign_string = _APP_SECRET + "".join(f"{k}{v}" for k, v in sorted_params) + _APP_SECRET
    return hmac.new(
        _APP_SECRET.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()


def _call(method: str, extra_params: dict) -> dict:
    """Make a signed API call. Returns the parsed JSON response."""
    params = {
        "method": method,
        "app_key": _APP_KEY,
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "sha256",
        "format": "json",
        "v": "2.0",
        **extra_params,
    }
    params["sign"] = _sign(params)
    resp = requests.get(_BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def search_products(keyword: str, max_results: int = 20) -> list[dict]:
    """Search AliExpress affiliate products by keyword."""
    if not _APP_KEY or not _APP_SECRET:
        raise EnvironmentError(
            "ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET not set in .env. "
            "Sign up at portals.aliexpress.com and apply for API access."
        )

    data = _call("aliexpress.affiliate.product.query", {
        "keywords": keyword,
        "page_no": 1,
        "page_size": min(max_results, 50),
        "sort": "SALE_PRICE_ASC",
        "target_currency": "USD",
        "target_language": "EN",
        "tracking_id": "default",
        "fields": "product_id,product_title,sale_price,original_price,"
                  "evaluate_rate,lastest_volume,product_main_image_url,"
                  "product_detail_url,second_level_category_name",
    })

    resp_key = "aliexpress_affiliate_product_query_response"
    products_data = (
        data.get(resp_key, {})
            .get("resp_result", {})
            .get("result", {})
            .get("products", {})
            .get("product", [])
    ) or []

    products = []
    for p in products_data[:max_results]:
        try:
            price = float(str(p.get("sale_price", "0")).replace("$", "").strip())
        except ValueError:
            price = 0.0

        products.append({
            "id": str(p.get("product_id", "")),
            "title": p.get("product_title", ""),
            "supplier_price_usd": price,
            "shipping_weight_lbs": None,
            "review_count": float(str(p.get("evaluate_rate", "0")).replace("%", "") or 0),
            "orders_count": int(p.get("lastest_volume", 0) or 0),
            "image_urls": [p.get("product_main_image_url", "")],
            "product_url": p.get("product_detail_url", ""),
        })

    return products


def get_product_detail(product_id: str) -> dict:
    """Fetch additional detail for a single product."""
    if not _APP_KEY or not _APP_SECRET:
        return {}

    data = _call("aliexpress.affiliate.productdetail.get", {
        "product_ids": product_id,
        "target_currency": "USD",
        "target_language": "EN",
        "tracking_id": "default",
        "fields": "product_id,product_main_image_url,product_video,detail",
    })

    resp_key = "aliexpress_affiliate_productdetail_get_response"
    products = (
        data.get(resp_key, {})
            .get("resp_result", {})
            .get("result", {})
            .get("products", {})
            .get("product", [])
    ) or []

    if not products:
        return {}

    p = products[0]
    return {
        "image_urls": [p.get("product_main_image_url", "")],
        "shipping_weight_lbs": None,  # not available in affiliate API
        "description_html": "",
    }


def _parse_orders(trade_desc: str) -> int:
    """Parse '1.2k+ sold' → 1200."""
    if not trade_desc:
        return 0
    s = str(trade_desc).lower().replace("sold", "").replace("+", "").strip()
    try:
        if "k" in s:
            return int(float(s.replace("k", "")) * 1000)
        return int(float(s))
    except ValueError:
        return 0
