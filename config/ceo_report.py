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
           *, cost_usd: float | None = None, duration_ms: int | None = None) -> None:
    secret = os.environ.get("CEOS_REPORT_SECRET", "").strip()
    if not secret:
        return
    base = os.environ.get("CEOS_DASHBOARD_URL", DEFAULT_URL).strip().rstrip("/")
    try:
        requests.post(
            f"{base}/api/report",
            headers={"x-report-secret": secret, "content-type": "application/json"},
            json={
                "agentId": AGENT_ID,
                "status": {
                    "state": state,
                    "lastRun": datetime.now(timezone.utc).isoformat(),
                    "summary": summary[:280],
                    "ok": ok,
                },
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[ceo_report] post failed: {e}")
