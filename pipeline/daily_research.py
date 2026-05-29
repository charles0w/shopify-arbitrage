"""
Daily product research run.

What it does:
  1. Runs research across all configured niches
  2. Scores and filters products (MIN_SCORE threshold)
  3. Generates Claude listing copy for each product
  4. Saves results to queue/YYYY-MM-DD.json + .md
  5. Syncs to Supabase so the dashboard can show/approve them

Run: python -m pipeline.daily_research
"""
import json
import os
import sys
import time
import traceback
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import MAX_QUEUE_SIZE
from research.product_scorer import research_all_niches
from listing.listing_generator import generate_listing
from auth.shopify_token import get_token

QUEUE_DIR = Path(__file__).parent.parent / "queue"
QUEUE_DIR.mkdir(exist_ok=True)

_INSERT_RETRY_BACKOFF_S = (0.5, 1.5, 4.0)


def _post_webhook(text: str):
    """POST to DIGEST_WEBHOOK_URL if configured. Slack/Discord-compatible.
    Failures here are logged and swallowed — the alert path must never crash
    the run."""
    url = os.environ.get("DIGEST_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(url, json={"text": text}, timeout=10)
    except Exception as e:
        print(f"[daily_research] Webhook post failed: {e}")


def _post_digest(today: str, items: list[dict]):
    """Successful run summary."""
    dashboard = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    queue_link = f"{dashboard}/queue?date={today}" if dashboard else ""

    lines = [f"*Arbitrage research — {today}*", f"{len(items)} products queued."]
    for i, p in enumerate(items[:3]):
        title = (p.get("listing_title") or p.get("title") or "")[:80]
        lines.append(
            f"  {i+1}. {title} — score {p.get('score', 0):.2f} "
            f"(${p.get('supplier_price_usd', 0):.2f} → ${p.get('suggested_sale_price_usd', 0):.2f})"
        )
    if queue_link:
        lines.append(f"Approve: {queue_link}")
    _post_webhook("\n".join(lines))


def _post_zero_result_alert(today: str):
    """Distinct alert when scoring drops everything below threshold — easy to
    miss in a normal-looking 'X products queued' digest, but it usually means
    something is broken (pytrends rate-limited, niches gone stale, supplier
    prices outside markup tiers)."""
    _post_webhook(
        f":warning: Arbitrage research — {today}: 0 products queued. "
        f"Likely causes: pytrends rate-limited, niche keywords no longer "
        f"score above MIN_SCORE, or CJ search returning empty. "
        f"Check the GH Actions log."
    )


def _post_failure_alert(today: str, exc: BaseException):
    """Loud alert when daily_research itself crashes. Without this a red CI
    job is the only signal and it's easy to miss for a day."""
    tb = traceback.format_exc()
    summary = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
    _post_webhook(
        f":rotating_light: Arbitrage research FAILED — {today}\n"
        f"{type(exc).__name__}: {summary}\n"
        f"```\n{tb[-1500:]}\n```"
    )


def _insert_with_retry(sb, rows: list[dict]):
    """Retry the queue_items insert on transient Supabase failure. Same
    backoff pattern as fulfillment._supabase_retry. Logs each attempt."""
    last_exc: Exception | None = None
    for attempt in range(len(_INSERT_RETRY_BACKOFF_S) + 1):
        try:
            return sb.table("queue_items").insert(rows).execute()
        except Exception as exc:
            last_exc = exc
            if attempt < len(_INSERT_RETRY_BACKOFF_S):
                print(f"[daily_research] Supabase insert attempt "
                      f"{attempt + 1} failed: {exc} — retrying")
                time.sleep(_INSERT_RETRY_BACKOFF_S[attempt])
            else:
                print(f"[daily_research] Supabase insert gave up after "
                      f"{attempt + 1} attempts: {exc}")
    assert last_exc is not None
    raise last_exc


def _filter_already_in_today(sb, today: str, rows: list[dict]) -> list[dict]:
    """Drop rows whose cj_product_id already exists in queue_items for `today`.

    Same-day reruns (manual workflow_dispatch after the morning cron, or a
    cron retry) would otherwise insert duplicates with no unique constraint
    to catch them. Existing rows are left untouched — pending stays pending,
    approved stays approved with its shopify_product_id.
    """
    if not rows:
        return rows
    res = sb.table("queue_items").select("cj_product_id").eq("date", today).execute()
    existing = {r["cj_product_id"] for r in (res.data or []) if r.get("cj_product_id")}
    if not existing:
        return rows
    return [r for r in rows if r.get("cj_product_id") not in existing]


def _supabase_client():
    """Return a Supabase client if credentials are configured, else None."""
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if url and key:
            return create_client(url, key)
    except ImportError:
        pass
    return None


def run():
    today = date.today().isoformat()
    try:
        return _run(today)
    except Exception as exc:
        _post_failure_alert(today, exc)
        raise  # re-raise so the GH Actions job is marked failed too


def _run(today: str):
    json_path = QUEUE_DIR / f"{today}.json"
    md_path = QUEUE_DIR / f"{today}.md"

    get_token()  # refresh Shopify token before any API calls
    print(f"[daily_research] Starting niche research — {today}")
    products = research_all_niches(top_n=3)
    top = products[:MAX_QUEUE_SIZE]

    # Generate Claude listings for each product
    print(f"[daily_research] Generating listings for {len(top)} products...")
    enriched = []
    for i, p in enumerate(top):
        print(f"  [{i+1}/{len(top)}] {p['title'][:60]}")
        try:
            listing = generate_listing(p)
            p["listing_title"] = listing.get("title", "")
            p["listing_body_html"] = listing.get("body_html", "")
            p["listing_tags"] = listing.get("tags", [])
            p["listing_meta_title"] = listing.get("meta_title", "")
            p["listing_meta_description"] = listing.get("meta_description", "")
        except Exception as e:
            print(f"    Listing gen failed: {e}")
            p["listing_title"] = None
            p["listing_body_html"] = None
            p["listing_tags"] = []
            p["listing_meta_title"] = None
            p["listing_meta_description"] = None
        enriched.append(p)

    # Save local JSON queue
    with open(json_path, "w") as f:
        json.dump(enriched, f, indent=2)

    # Write Obsidian-readable markdown queue
    lines = [
        f"# Green-Light Queue — {today}",
        "",
        f"**{len(enriched)} products found above score threshold.**",
        "Approve via the Vercel dashboard or run `python -m pipeline.approve`.",
        "",
    ]
    for i, p in enumerate(enriched):
        breakdown = p.get("score_breakdown", {})
        lines += [
            f"## [{i}] {p.get('listing_title') or p['title'][:80]}",
            "",
            f"- **Score:** {p['score']} "
            f"(margin {breakdown.get('margin_gap',0):.2f} · "
            f"trend {breakdown.get('trend_velocity',0):.2f} · "
            f"reviews {breakdown.get('review_volume',0):.2f} · "
            f"weight {breakdown.get('shipping_weight',0):.2f})",
            f"- **Supplier price:** ${p.get('supplier_price_usd', 0):.2f}",
            f"- **Suggested sale price:** ${p.get('suggested_sale_price_usd', 0):.2f}  "
            f"({p.get('markup', 0):.1f}×)",
            f"- **Niche keyword:** {p.get('keyword', '')}",
            f"- **CJ link:** {p.get('product_url', '')}",
            f"- **Orders:** {p.get('orders_count', 0):,}",
            "",
        ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[daily_research] Saved locally: {json_path}")

    # Sync to Supabase
    sb = _supabase_client()
    if sb:
        rows = [
            {
                "date": today,
                "cj_product_id": p.get("id", ""),
                "title": p.get("title", ""),
                "supplier_price_usd": p.get("supplier_price_usd", 0),
                "suggested_sale_price_usd": p.get("suggested_sale_price_usd", 0),
                "score": p.get("score", 0),
                "keyword": p.get("keyword", ""),
                "product_url": p.get("product_url", ""),
                "image_url": (p.get("image_urls") or [""])[0],
                "image_urls": p.get("image_urls") or [],
                "listing_title": p.get("listing_title"),
                "listing_body_html": p.get("listing_body_html"),
                "listing_tags": p.get("listing_tags", []),
                "listing_meta_title": p.get("listing_meta_title"),
                "listing_meta_description": p.get("listing_meta_description"),
                "status": "pending",
            }
            for p in enriched
        ]
        before = len(rows)
        rows = _filter_already_in_today(sb, today, rows)
        skipped = before - len(rows)
        if skipped:
            print(f"[daily_research] Skipped {skipped} cj_product_id(s) "
                  f"already in queue_items for {today} (rerun)")
        if rows:
            _insert_with_retry(sb, rows)
            print(f"[daily_research] Synced {len(rows)} items to Supabase.")
        else:
            print(f"[daily_research] All {before} researched products were "
                  f"already in today's queue — nothing to insert.")
    else:
        print("[daily_research] No Supabase credentials — skipping cloud sync.")
        print("  Add SUPABASE_URL and SUPABASE_SERVICE_KEY to .env to enable dashboard.")

    if enriched:
        _post_digest(today, enriched)
    else:
        _post_zero_result_alert(today)

    print(f"[daily_research] Done. {len(enriched)} products queued.")
    return enriched


if __name__ == "__main__":
    run()
