"""Report this agent's run status to the CEO's Enterprise fleet dashboard.

POSTs to {CEOS_DASHBOARD_URL}/api/report with a shared-secret header so the
`commerce` card on ceos-enterprise reflects this repo's real autonomous runs
(daily research, fulfillment ticks, weekly reprice).

Mirrors the swallow-all-errors style of the pipeline's _post_webhook helpers —
status reporting must never crash a fulfillment or research run. No-ops when
CEOS_REPORT_SECRET isn't set (e.g. local dev, CI tests), so it's safe to call
unconditionally.

Note: deliberately does NOT reuse DASHBOARD_URL — that points at this repo's
own Vercel dashboard, not the CEO control plane.
"""
import os

import requests

AGENT_ID = "commerce"
DEFAULT_URL = "https://ceos-enterprise.vercel.app"


def report(state: str, summary: str = "", ok: bool = True,
           *, cost_usd: float | None = None, duration_ms: int | None = None) -> None:
    secret = os.environ.get("CEOS_REPORT_SECRET", "").strip()
    if not secret:
        return  # not wired up — skip silently, same as the digest webhook poster
    base = os.environ.get("CEOS_DASHBOARD_URL", DEFAULT_URL).strip().rstrip("/")
    try:
        requests.post(
            f"{base}/api/report",
            headers={"x-report-secret": secret, "content-type": "application/json"},
            json={
                "agentId": AGENT_ID,
                "state": state,
                "summary": summary[:280],
                "ok": ok,
                "costUsd": cost_usd,
                "durationMs": duration_ms,
            },
            timeout=10,
        )
    except Exception as e:  # reporting must never crash the caller
        print(f"[ceo_report] post failed: {e}")
