"""Report this agent's run status to the CEO's Enterprise fleet dashboard.

POSTs to {CEOS_DASHBOARD_URL}/api/report with a shared-secret header so the
`commerce` card on ceos-enterprise reflects this repo's real autonomous runs
(daily research, fulfillment ticks, weekly reprice).

Never raises — status reporting must never crash a fulfillment or research run.
No-ops when CEOS_REPORT_SECRET isn't set (local dev, CI tests).
"""
import os
from datetime import datetime, timezone

import requests

AGENT_ID = "commerce"
DEFAULT_URL = "https://ceos-enterprise.vercel.app"


def report(state: str, summary: str = "", ok: bool = True,
           *, cost_usd: float | None = None, duration_ms: int | None = None,
           metrics: list[dict] | None = None, progress: float | None = None,
           profit: float | None = None, profit_note: str | None = None) -> None:
    """metrics: up to 3 {"label", "value", "unit"?, "money"?, "signed"?} card
    numbers; progress: 0..1 through the current task; profit: REALIZED profit
    in USD for this run (funds The Garage — send once per realized win, never
    on routine heartbeats)."""
    secret = os.environ.get("CEOS_REPORT_SECRET", "").strip()
    if not secret:
        return
    base = os.environ.get("CEOS_DASHBOARD_URL", DEFAULT_URL).strip().rstrip("/")
    status: dict = {
        "state": state,
        "lastRun": datetime.now(timezone.utc).isoformat(),
        "summary": summary[:280],
        "ok": ok,
    }
    if metrics:
        status["metrics"] = metrics[:3]
    if progress is not None:
        status["progress"] = max(0.0, min(1.0, float(progress)))
    payload: dict = {"agentId": AGENT_ID, "status": status}
    if profit is not None and float(profit) != 0.0:
        payload["profit"] = {"amount": round(float(profit), 2)}
        if profit_note:
            payload["profit"]["note"] = profit_note[:200]
    try:
        requests.post(
            f"{base}/api/report",
            headers={"x-report-secret": secret, "content-type": "application/json"},
            json=payload,
            timeout=10,
        )
    except Exception as e:
        print(f"[ceo_report] post failed: {e}")
