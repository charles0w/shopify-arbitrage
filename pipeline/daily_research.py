"""
Daily product research run.

What it does:
  1. Runs research across all configured niches
  2. Scores and filters products (MIN_SCORE threshold)
  3. Saves results to queue/YYYY-MM-DD.json
  4. Writes a human-readable queue/YYYY-MM-DD.md for Obsidian review

Run: python -m pipeline.daily_research
"""
import json
import sys
import os
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import MAX_QUEUE_SIZE
from research.product_scorer import research_all_niches

QUEUE_DIR = Path(__file__).parent.parent / "queue"
QUEUE_DIR.mkdir(exist_ok=True)


def run():
    today = date.today().isoformat()
    json_path = QUEUE_DIR / f"{today}.json"
    md_path = QUEUE_DIR / f"{today}.md"

    print(f"[daily_research] Starting niche research — {today}")
    products = research_all_niches(top_n=3)
    top = products[:MAX_QUEUE_SIZE]

    # Save JSON queue
    with open(json_path, "w") as f:
        json.dump(top, f, indent=2)

    # Write Obsidian-readable markdown queue
    lines = [
        f"# Green-Light Queue — {today}",
        "",
        f"**{len(top)} products found above score threshold.**",
        "Review each product below and run `python -m pipeline.approve {date} <indices>` to approve.",
        "",
    ]

    for i, p in enumerate(top):
        breakdown = p.get("score_breakdown", {})
        lines += [
            f"## [{i}] {p['title'][:80]}",
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
            f"- **AliExpress link:** {p.get('product_url', '')}",
            f"- **Orders:** {p.get('orders_count', 0):,}",
            "",
        ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[daily_research] Done. {len(top)} products queued.")
    print(f"  JSON: {json_path}")
    print(f"  Review: {md_path}")
    return top


if __name__ == "__main__":
    run()
