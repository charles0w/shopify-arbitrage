"""
Place orders on CJDropshipping and poll for tracking numbers.
Reuses the auth token from research/aliexpress_fetcher.py.
"""
import time

import requests
from research.aliexpress_fetcher import _headers, _is_auth_error, _BASE

_RETRY_BACKOFF_S = (2, 4, 8)  # one entry per attempt after the first


def _post_with_retry(url: str, *, headers: dict, json: dict, timeout: int = 30):
    """POST that retries on 5xx and network errors with exponential backoff.

    Returns the final Response (caller decides how to interpret 4xx). Raises
    the last exception if every attempt failed at the network layer.
    """
    last_exc: Exception | None = None
    for attempt in range(len(_RETRY_BACKOFF_S) + 1):
        try:
            resp = requests.post(url, headers=headers, json=json, timeout=timeout)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < len(_RETRY_BACKOFF_S):
                time.sleep(_RETRY_BACKOFF_S[attempt])
                continue
            raise

        if 500 <= resp.status_code < 600 and attempt < len(_RETRY_BACKOFF_S):
            time.sleep(_RETRY_BACKOFF_S[attempt])
            continue
        return resp

    # Unreachable — the loop either returns or raises — but mypy/pylint friendly.
    if last_exc:
        raise last_exc
    raise RuntimeError("retry loop exited without response")


def get_cj_variants(pid: str) -> list[dict]:
    """Return variant list for a CJ product pid."""
    resp = requests.get(
        f"{_BASE}/product/query",
        headers=_headers(),
        params={"pid": pid},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("result"):
        return []
    return data.get("data", {}).get("variants", [])


def get_cheapest_shipping(vid: str, country_code: str = "US") -> str:
    """Return cheapest available CJ shipping method name for a variant to a country.

    Raises RuntimeError when CJ doesn't return any methods for the destination
    (e.g. unsupported country, deleted variant). The caller should let this
    propagate so mark_error captures the real reason — falling back silently
    to a hardcoded method just shifts the failure to place_cj_order with a
    less informative message.
    """
    resp = requests.post(
        f"{_BASE}/logistics/freightCalculate",
        headers=_headers(),
        json={
            "startCountryCode": "CN",
            "endCountryCode": country_code,
            "quantity": 1,
            "vid": vid,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    options = data.get("data", []) or []
    if not options:
        raise RuntimeError(
            f"CJ returned no shipping methods for vid={vid} to {country_code}"
        )
    options.sort(key=lambda x: float(x.get("logisticPrice", 9999)))
    name = options[0].get("logisticName", "")
    if not name:
        raise RuntimeError(
            f"CJ shipping option missing logisticName for vid={vid} to {country_code}"
        )
    return name


def place_cj_order(shopify_order: dict, cj_items: list[dict]) -> str:
    """
    Place a CJDropshipping order. Returns the CJ order ID.

    cj_items: list of {vid, quantity, shipping_name}
    shopify_order: full Shopify order dict (needs shipping_address)
    """
    addr = shopify_order.get("shipping_address") or {}
    address_line = addr.get("address1", "")
    if addr.get("address2"):
        address_line += " " + addr["address2"]

    payload = {
        "orderList": [
            {
                "vid": item["vid"],
                "quantity": item["quantity"],
                "shippingName": item["shipping_name"],
            }
            for item in cj_items
        ],
        "shippingAddress": {
            "shippingCountry": addr.get("country", "United States"),
            "shippingCountryCode": addr.get("country_code", "US"),
            "shippingProvince": addr.get("province", ""),
            "shippingCity": addr.get("city", ""),
            "shippingAddress": address_line.strip(),
            "shippingZip": addr.get("zip", ""),
            "shippingCustomerName": addr.get("name", ""),
            "shippingPhone": addr.get("phone", ""),
        },
        "remark": f"Shopify {shopify_order.get('name', shopify_order['id'])}",
    }

    url = f"{_BASE}/shopping/order/createOrder"
    resp = _post_with_retry(url, headers=_headers(), json=payload)
    if _is_auth_error(resp):
        # Cached token rejected — refresh once and retry.
        resp = _post_with_retry(
            url, headers=_headers(force_refresh=True), json=payload
        )

    resp.raise_for_status()
    data = resp.json()

    if not data.get("result"):
        raise RuntimeError(f"CJ order creation failed: {data.get('message')}")

    return data["data"]["orderId"]


def get_order_tracking(cj_order_id: str) -> dict | None:
    """
    Check a CJ order for tracking. Returns {tracking_number, carrier, status}
    once shipped, otherwise None.
    """
    resp = requests.get(
        f"{_BASE}/shopping/order/getOrderDetail",
        headers=_headers(),
        params={"orderId": cj_order_id},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("result"):
        return None

    order = data.get("data", {})
    status = order.get("orderStatus", "")

    if status in ("SHIPPED", "DELIVERED", "IN_TRANSIT"):
        track = order.get("trackNumber") or order.get("trackingNumber", "")
        if track:
            return {
                "tracking_number": track,
                "carrier": order.get("shippingCarrier") or order.get("logisticName", "CJ Packet"),
                "status": status,
            }

    return None
