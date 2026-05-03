"""
Poll Shopify for new paid+unfulfilled orders and manage fulfillment state.
State is persisted locally to fulfillment_state.json AND synced to Supabase
(if SUPABASE_URL + SUPABASE_SERVICE_KEY are set in .env).
"""
import json
import os
import time
from pathlib import Path

import requests
from config.settings import SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN

_BASE = f"https://{SHOPIFY_STORE_URL}/admin/api/2024-01"
_HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json",
}
_STATE = Path(__file__).parent.parent / "fulfillment_state.json"

_SUPABASE_RETRY_BACKOFF_S = (0.5, 1.5, 4.0)  # 4 attempts total


def _supabase_retry(op, label: str):
    """Execute a Supabase operation with retries on transient failure.

    `op` is a zero-arg callable that performs the .execute() call. We retry
    on any exception with exponential backoff. After the final attempt the
    last exception is re-raised so callers see the failure rather than
    silently dropping the write — silent drops here cause duplicate CJ
    orders on the next stateless cron tick.
    """
    last_exc: Exception | None = None
    for attempt in range(len(_SUPABASE_RETRY_BACKOFF_S) + 1):
        try:
            return op()
        except Exception as exc:
            last_exc = exc
            if attempt < len(_SUPABASE_RETRY_BACKOFF_S):
                print(
                    f"[order_monitor] Supabase {label} attempt {attempt + 1} "
                    f"failed: {exc} — retrying"
                )
                time.sleep(_SUPABASE_RETRY_BACKOFF_S[attempt])
            else:
                print(
                    f"[order_monitor] Supabase {label} gave up after "
                    f"{attempt + 1} attempts: {exc}"
                )
    assert last_exc is not None
    raise last_exc


# ── Local state helpers ─────────────────────────────────────────────────────

def _load_state() -> dict:
    if _STATE.exists():
        with open(_STATE) as f:
            state = json.load(f)
    else:
        state = {"fulfilled_order_ids": [], "pending_tracking": []}

    # In stateless environments (e.g. GitHub Actions) the local file is empty
    # on every run. Use Supabase as the source of truth so we don't re-place
    # CJ orders that are still in the cj-placed-but-not-shipped window, and
    # so check_tracking() can resume polling for shipments.
    sb = _sb()
    if sb:
        # Fail loud if this can't read — silently returning empty
        # fulfilled_order_ids would cause the stateless tick to re-attempt
        # every paid+unfulfilled Shopify order on CJ, doubling them up.
        res = _supabase_retry(
            lambda: sb.table("fulfillments").select(
                "shopify_order_id, cj_order_id, status"
            ).execute(),
            label="state merge",
        )
        rows = res.data or []
        ids = {r["shopify_order_id"] for r in rows if r.get("shopify_order_id")}
        ids.update(str(i) for i in state["fulfilled_order_ids"])
        state["fulfilled_order_ids"] = list(ids)

        local_pending_cj = {p["cj_order_id"] for p in state["pending_tracking"]}
        for r in rows:
            if (
                r.get("status") == "cj_placed"
                and r.get("cj_order_id")
                and r["cj_order_id"] not in local_pending_cj
            ):
                state["pending_tracking"].append({
                    "shopify_order_id": r["shopify_order_id"],
                    "cj_order_id": r["cj_order_id"],
                    "submitted_at": 0,
                })

    return state


def _save_state(state: dict):
    with open(_STATE, "w") as f:
        json.dump(state, f, indent=2)


# ── Supabase sync (optional) ─────────────────────────────────────────────────

def _sb():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if url and key:
            return create_client(url, key)
    except ImportError:
        pass
    return None


# ── Shopify helpers ─────────────────────────────────────────────────────────

def get_new_orders() -> list[dict]:
    """Return paid+unfulfilled Shopify orders not yet sent to CJ."""
    state = _load_state()
    done = set(str(i) for i in state["fulfilled_order_ids"])

    resp = requests.get(
        f"{_BASE}/orders.json",
        headers=_HEADERS,
        params={
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "status": "open",
            "limit": 50,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return [o for o in resp.json().get("orders", []) if str(o["id"]) not in done]


def get_product_metafields(product_id: int) -> dict:
    """Return {namespace.key: value} for all metafields on a Shopify product."""
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


def mark_fulfilled(shopify_order_id: int, cj_order_id: str, order: dict | None = None):
    state = _load_state()
    state["fulfilled_order_ids"].append(str(shopify_order_id))
    state["pending_tracking"].append({
        "shopify_order_id": str(shopify_order_id),
        "cj_order_id": cj_order_id,
        "submitted_at": time.time(),
    })
    _save_state(state)

    sb = _sb()
    if sb:
        row = {
            "shopify_order_id": str(shopify_order_id),
            "shopify_order_name": order.get("name", "") if order else "",
            "shopify_order_total": float(order.get("total_price", 0)) if order else 0,
            "cj_order_id": cj_order_id,
            "status": "cj_placed",
        }
        _supabase_retry(
            lambda: sb.table("fulfillments").upsert(row, on_conflict="shopify_order_id").execute(),
            label=f"mark_fulfilled({shopify_order_id})",
        )


def mark_error(shopify_order_id: int, error_message: str, order: dict | None = None):
    """Record a failed CJ order placement so it surfaces in the dashboard.

    Adds the Shopify order ID to fulfilled_order_ids so the next poll doesn't
    immediately retry — the operator should resolve the error and clear/retry
    manually. Upserts a fulfillments row with status='error'.
    """
    state = _load_state()
    if str(shopify_order_id) not in state["fulfilled_order_ids"]:
        state["fulfilled_order_ids"].append(str(shopify_order_id))
    _save_state(state)

    sb = _sb()
    if sb:
        row = {
            "shopify_order_id": str(shopify_order_id),
            "shopify_order_name": order.get("name", "") if order else "",
            "shopify_order_total": float(order.get("total_price", 0)) if order else 0,
            "status": "error",
            "error_message": error_message[:500],  # bound for the column
        }
        _supabase_retry(
            lambda: sb.table("fulfillments").upsert(row, on_conflict="shopify_order_id").execute(),
            label=f"mark_error({shopify_order_id})",
        )


def get_pending_tracking() -> list[dict]:
    return _load_state()["pending_tracking"]


def drop_tracking_entry(cj_order_id: str):
    state = _load_state()
    state["pending_tracking"] = [
        t for t in state["pending_tracking"] if t["cj_order_id"] != cj_order_id
    ]
    _save_state(state)


def update_tracking_in_supabase(shopify_order_id: str, tracking_number: str, carrier: str):
    sb = _sb()
    if sb:
        _supabase_retry(
            lambda: sb.table("fulfillments").update({
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status": "shipped",
                "error_message": None,  # clear stale tracking-push error if any
                "updated_at": "now()",
            }).eq("shopify_order_id", shopify_order_id).execute(),
            label=f"update_tracking({shopify_order_id})",
        )


def mark_tracking_failed(shopify_order_id: str, error_message: str) -> bool:
    """Record that we couldn't push tracking back to Shopify even though CJ has
    shipped. Keeps status='cj_placed' (the CJ order itself is fine — it's the
    Shopify-side fulfillment write that failed) but sets error_message so the
    dashboard surfaces it.

    Returns True if this is a new failure (error_message was previously empty
    or different) so the caller can decide whether to alert. Avoids re-alerting
    on every cron tick for the same persistent failure.
    """
    sb = _sb()
    if not sb:
        return True  # no Supabase, can't dedupe — alert each time

    bounded = error_message[:500]
    existing = _supabase_retry(
        lambda: sb.table("fulfillments").select("error_message").eq(
            "shopify_order_id", str(shopify_order_id)
        ).limit(1).execute(),
        label=f"mark_tracking_failed read({shopify_order_id})",
    )
    rows = existing.data or []
    prev = rows[0].get("error_message") if rows else None

    _supabase_retry(
        lambda: sb.table("fulfillments").update({
            "error_message": bounded,
            "updated_at": "now()",
        }).eq("shopify_order_id", str(shopify_order_id)).execute(),
        label=f"mark_tracking_failed write({shopify_order_id})",
    )

    return prev != bounded


def push_tracking_to_shopify(shopify_order_id: str, tracking_number: str, carrier: str):
    """Create a Shopify fulfillment with the CJ tracking number."""
    resp = requests.get(
        f"{_BASE}/orders/{shopify_order_id}/fulfillment_orders.json",
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    open_fos = [
        fo for fo in resp.json().get("fulfillment_orders", [])
        if fo["status"] == "open"
    ]

    if not open_fos:
        print(f"    No open fulfillment orders for Shopify order {shopify_order_id}")
        return

    payload = {
        "fulfillment": {
            "message": f"Shipped via {carrier}",
            "notify_customer": True,
            "tracking_info": {
                "number": tracking_number,
                "company": carrier,
            },
            "line_items_by_fulfillment_order": [
                {
                    "fulfillment_order_id": fo["id"],
                    "fulfillment_order_line_items": [
                        {"id": li["id"], "quantity": li["fulfillable_quantity"]}
                        for li in fo.get("line_items", [])
                    ],
                }
                for fo in open_fos
            ],
        }
    }

    resp = requests.post(
        f"{_BASE}/fulfillments.json",
        json=payload,
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()

    # Mirror to Supabase
    update_tracking_in_supabase(shopify_order_id, tracking_number, carrier)
    return resp.json()
