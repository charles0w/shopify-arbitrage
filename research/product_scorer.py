"""
Score AliExpress products and return a ranked list for the green-light queue.

Scoring formula (weights from config/settings.py):
  margin_gap      — estimated sale price vs supplier cost (markup ratio)
  trend_velocity  — Google Trends score for product keyword
  review_volume   — normalised AliExpress review/orders count
  shipping_weight — penalise heavy products (> 2 lbs)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import (
    WEIGHTS, MIN_SCORE, MARKUP, DEFAULT_MARKUP, NICHES,
    MIN_SALE_PRICE, MIN_PROFIT_USD,
)
from research.trend_fetcher import trend_score
from research.aliexpress_fetcher import search_products, get_product_detail


def _markup_for(cost: float) -> float:
    for threshold in sorted(MARKUP):
        if cost < threshold:
            return MARKUP[threshold]
    return DEFAULT_MARKUP


def _margin_gap_score(supplier_price: float) -> float:
    """How good is the margin at this supplier price?
    Higher markup multiplier = higher score. Normalise to 0–1."""
    if supplier_price <= 0:
        return 0.0
    markup = _markup_for(supplier_price)
    # Markup range: 2.0 (worst) to 4.0 (best) → normalise
    return round((markup - 2.0) / 2.0, 4)


def _review_score(orders: int, reviews: float) -> float:
    """Normalised social proof. Cap at 10k orders = 1.0."""
    combined = orders + (reviews * 10)
    return round(min(combined / 10_000, 1.0), 4)


def _weight_score(weight_lbs: float | None) -> float:
    """1.0 if weight unknown or ≤ 0.5 lbs, penalise linearly up to 0 at 3 lbs."""
    if weight_lbs is None:
        return 0.5  # unknown — assume medium
    if weight_lbs <= 0.5:
        return 1.0
    if weight_lbs >= 3.0:
        return 0.0
    return round(1.0 - (weight_lbs - 0.5) / 2.5, 4)


def score_product(product: dict, keyword: str, _trend: float | None = None) -> dict:
    """Score a single product. Enriches with detail if weight is missing.

    Pass _trend to reuse a precomputed trend score (avoids duplicate pytrends
    calls when scoring many products for the same niche keyword).
    """
    if product.get("shipping_weight_lbs") is None and product.get("id"):
        try:
            detail = get_product_detail(product["id"])
            product.update({
                "shipping_weight_lbs": detail.get("shipping_weight_lbs"),
                "image_urls": detail.get("image_urls") or product.get("image_urls", []),
            })
        except Exception:
            pass

    trend = _trend if _trend is not None else trend_score(keyword)
    margin = _margin_gap_score(product.get("supplier_price_usd", 0))
    reviews = _review_score(
        product.get("orders_count", 0), product.get("review_count", 0)
    )
    weight = _weight_score(product.get("shipping_weight_lbs"))

    total = (
        WEIGHTS["margin_gap"] * margin
        + WEIGHTS["trend_velocity"] * trend
        + WEIGHTS["review_volume"] * reviews
        + WEIGHTS["shipping_weight"] * weight
    )

    markup = _markup_for(product.get("supplier_price_usd", 0))
    sale_price = round(product.get("supplier_price_usd", 0) * markup, 2)

    return {
        **product,
        "keyword": keyword,
        "score": round(total, 4),
        "score_breakdown": {
            "margin_gap": margin,
            "trend_velocity": trend,
            "review_volume": reviews,
            "shipping_weight": weight,
        },
        "suggested_sale_price_usd": sale_price,
        "markup": markup,
    }


def research_niche(keyword: str, max_products: int = 25) -> list[dict]:
    """Fetch + score products for a keyword. Return those above MIN_SCORE that
    also clear the hard quality gates (MIN_SALE_PRICE, MIN_PROFIT_USD), ranked."""
    products = search_products(keyword, max_results=max_products)

    # Prioritise products with proven demand so the top_n we keep are the
    # best-selling candidates, not just the first ones CJ happens to return.
    products.sort(key=lambda p: p.get("orders_count", 0), reverse=True)

    # Compute trend once — all products share the same niche keyword, so
    # calling trend_score per product would just hammer pytrends needlessly.
    niche_trend = trend_score(keyword)

    scored = [score_product(p, keyword, _trend=niche_trend) for p in products]

    qualified = []
    for p in scored:
        if p["score"] < MIN_SCORE:
            continue
        sale = p["suggested_sale_price_usd"]
        profit = sale - p["supplier_price_usd"]
        if sale < MIN_SALE_PRICE:
            print(f"    [skip] ${sale:.2f} sale < ${MIN_SALE_PRICE:.2f} min — '{p['title'][:55]}'")
            continue
        if profit < MIN_PROFIT_USD:
            print(f"    [skip] ${profit:.2f} profit < ${MIN_PROFIT_USD:.2f} min — '{p['title'][:55]}'")
            continue
        qualified.append(p)

    return sorted(qualified, key=lambda x: x["score"], reverse=True)


def research_all_niches(top_n: int = 3) -> list[dict]:
    """Run research across all configured niches. Return top_n per niche."""
    import time
    results = []
    for i, niche in enumerate(NICHES):
        print(f"  [{i+1}/{len(NICHES)}] researching: {niche}")
        niche_results = research_niche(niche, max_products=25)
        results.extend(niche_results[:top_n])
        if i < len(NICHES) - 1:
            time.sleep(30)  # stay within RapidAPI free tier rate limit
    # Deduplicate by product ID
    seen = set()
    deduped = []
    for p in sorted(results, key=lambda x: x["score"], reverse=True):
        if p["id"] not in seen:
            seen.add(p["id"])
            deduped.append(p)
    return deduped
