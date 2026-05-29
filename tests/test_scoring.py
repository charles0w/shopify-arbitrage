"""
Tests for the money math: markup tiers, margin/review/weight subscores.

These are the calculations that decide what we charge customers, so a silent
arithmetic regression here would directly mis-price live listings.
"""
import pytest

from research.product_scorer import (
    _markup_for,
    _margin_gap_score,
    _review_score,
    _weight_score,
)
from pipeline import weekly_reprice


# ── Markup tiers ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cost,expected", [
    (0.01, 4.0),
    (4.99, 4.0),
    (5.00, 3.0),    # boundary: cost < 5 → tier 5; cost == 5 → tier 15
    (14.99, 3.0),
    (15.00, 2.5),
    (29.99, 2.5),
    (30.00, 2.0),   # DEFAULT_MARKUP kicks in
    (100.00, 2.0),
])
def test_markup_tiers(cost, expected):
    assert _markup_for(cost) == expected


def test_weekly_reprice_markup_matches_scorer():
    """Both modules duplicate the markup tiers — make sure they stay in sync."""
    for cost in [0.5, 4.99, 5, 10, 14.99, 15, 25, 30, 100]:
        assert weekly_reprice._markup_for(cost) == _markup_for(cost), cost


# ── Margin gap score ────────────────────────────────────────────────────────

@pytest.mark.parametrize("price,expected", [
    (0, 0.0),
    (-5, 0.0),
    (3.0, 1.0),     # markup 4.0 → (4-2)/2 = 1.0
    (10.0, 0.5),    # markup 3.0 → (3-2)/2 = 0.5
    (20.0, 0.25),   # markup 2.5 → (2.5-2)/2 = 0.25
    (50.0, 0.0),    # markup 2.0 → (2-2)/2 = 0.0
])
def test_margin_gap_score(price, expected):
    assert _margin_gap_score(price) == expected


# ── Review score ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("orders,reviews,expected", [
    (0, 0, 0.0),
    (10_000, 0, 1.0),
    (5_000, 100, 0.6),       # (5000 + 1000) / 10000
    (50_000, 0, 1.0),        # capped
    (1_000, 50, 0.15),       # (1000 + 500) / 10000
    (0, 1_000, 1.0),         # reviews-only path: 1000 * 10 = 10000
])
def test_review_score(orders, reviews, expected):
    assert _review_score(orders, reviews) == expected


# ── Weight score ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lbs,expected", [
    (None, 0.5),
    (0.0, 1.0),
    (0.5, 1.0),
    (1.0, 0.8),     # 1 - (0.5 / 2.5)
    (2.0, 0.4),     # 1 - (1.5 / 2.5)
    (3.0, 0.0),
    (5.0, 0.0),
])
def test_weight_score(lbs, expected):
    assert _weight_score(lbs) == expected


# ── Sale-price formula round-trip ───────────────────────────────────────────

def test_sale_price_round_trip():
    """sale_price = supplier_price * markup, rounded to cents.
    Verifies the same calculation daily_research and weekly_reprice both rely on."""
    cases = [
        (1.00, 4.00),     # 1.00 × 4.0
        (3.27, 13.08),    # 3.27 × 4.0
        (10.00, 30.00),   # 10.00 × 3.0
        (20.00, 50.00),   # 20.00 × 2.5
        (50.00, 100.00),  # 50.00 × 2.0
    ]
    for supplier, expected in cases:
        markup = _markup_for(supplier)
        assert round(supplier * markup, 2) == expected, (supplier, markup)
