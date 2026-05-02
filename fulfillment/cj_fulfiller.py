"""
Place orders on CJDropshipping and poll for tracking numbers.
Reuses the auth token from research/aliexpress_fetcher.py.
"""
import requests
from research.aliexpress_fetcher import _headers, _BASE


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
    """Return cheapest available CJ shipping method name for a variant to a country."""
    try:
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
        if resp.status_code == 200:
            data = resp.json()
            options = data.get("data", []) or []
            if options:
                options.sort(key=lambda x: float(x.get("logisticPrice", 9999)))
                name = options[0].get("logisticName", "")
                if name:
                    return name
    except Exception:
        pass
    return "CJPacket Ordinary"


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

    resp = requests.post(
        f"{_BASE}/shopping/order/createOrder",
        headers=_headers(),
        json=payload,
        timeout=30,
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

    if status in ("SHIIPPED", "SHIPPED", "DELIVERED", "IN_TRANSIT"):
        track = order.get("trackNumber") or order.get("trackingNumber", "")
        if track:
            return {
                "tracking_number": track,
                "carrier": order.get("shippingCarrier") or order.get("logisticName", "CJ Packet"),
                "status": status,
            }

    return None
