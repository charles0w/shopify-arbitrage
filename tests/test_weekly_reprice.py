"""Tests for the weekly_reprice rewrite.

Before this rewrite, list_active_products didn't fetch metafields, so
product.get("metafields", []) was always empty and the cron silently
repriced zero variants every week. These tests cover the new metafield
fetch path, the retry behaviour, and the failure-alert wrapper.
"""
from unittest.mock import patch, MagicMock

import pytest

from pipeline import weekly_reprice


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    monkeypatch.setattr(weekly_reprice, "_RETRY_BACKOFF_S", (0, 0, 0))


def _product(pid: int, variants):
    return {"id": pid, "title": f"Product {pid}", "variants": variants}


# ── _update_price_with_retry ────────────────────────────────────────────────

def test_update_price_returns_immediately_on_success():
    with patch("pipeline.weekly_reprice.update_price", return_value=None) as up:
        weekly_reprice._update_price_with_retry(1, 2, 9.99)
    assert up.call_count == 1


def test_update_price_recovers_after_transient_failure():
    with patch(
        "pipeline.weekly_reprice.update_price",
        side_effect=[Exception("blip"), Exception("blip"), None],
    ) as up:
        weekly_reprice._update_price_with_retry(1, 2, 9.99)
    assert up.call_count == 3


def test_update_price_raises_after_max_attempts():
    with patch(
        "pipeline.weekly_reprice.update_price",
        side_effect=Exception("persistent"),
    ) as up:
        with pytest.raises(Exception, match="persistent"):
            weekly_reprice._update_price_with_retry(1, 2, 9.99)
    assert up.call_count == 4


# ── _run() reprices when metafield is present ───────────────────────────────

def test_run_reprices_when_supplier_price_metafield_present():
    """The bug-fix case: list_active_products doesn't return metafields, so
    we must call get_product_metafields per product to find supplier_price."""
    products = [_product(101, [{"id": 1001, "price": "20.00"}])]
    with patch("pipeline.weekly_reprice.list_active_products", return_value=products), \
         patch("pipeline.weekly_reprice.get_product_metafields",
               return_value={"arbitrage.supplier_price": "3.00"}), \
         patch("pipeline.weekly_reprice.update_price") as up, \
         patch("pipeline.weekly_reprice._post_webhook"):
        out = weekly_reprice._run()

    # supplier 3.00 × markup 4.0 = 12.00; current 20.00 — a >5% delta, so update fires
    up.assert_called_once_with(101, 1001, 12.00)
    assert out == {"updated": 1, "failed": 0, "skipped": 0}


def test_run_skips_when_no_supplier_metafield():
    products = [_product(102, [{"id": 1002, "price": "10.00"}])]
    with patch("pipeline.weekly_reprice.list_active_products", return_value=products), \
         patch("pipeline.weekly_reprice.get_product_metafields", return_value={}), \
         patch("pipeline.weekly_reprice.update_price") as up, \
         patch("pipeline.weekly_reprice._post_webhook"):
        out = weekly_reprice._run()

    up.assert_not_called()
    assert out == {"updated": 0, "failed": 0, "skipped": 1}


def test_run_within_5pct_does_not_reprice():
    """Existing behaviour preserved: only reprice if delta > 5%."""
    products = [_product(103, [{"id": 1003, "price": "12.30"}])]
    # supplier 3.00 × 4.0 = 12.00; current 12.30 → 2.5% delta → skip
    with patch("pipeline.weekly_reprice.list_active_products", return_value=products), \
         patch("pipeline.weekly_reprice.get_product_metafields",
               return_value={"arbitrage.supplier_price": "3.00"}), \
         patch("pipeline.weekly_reprice.update_price") as up, \
         patch("pipeline.weekly_reprice._post_webhook"):
        weekly_reprice._run()

    up.assert_not_called()


def test_run_one_failure_doesnt_abort_others():
    """Per-variant exception handling — one bad PUT shouldn't lose the
    rest of the batch."""
    products = [
        _product(201, [{"id": 2001, "price": "20.00"}]),
        _product(202, [{"id": 2002, "price": "20.00"}]),
    ]
    with patch("pipeline.weekly_reprice.list_active_products", return_value=products), \
         patch("pipeline.weekly_reprice.get_product_metafields",
               return_value={"arbitrage.supplier_price": "3.00"}), \
         patch(
             "pipeline.weekly_reprice.update_price",
             side_effect=[Exception("first dies"), None,
                          Exception("first dies"), None],
         ) as up, \
         patch("pipeline.weekly_reprice._post_webhook"):
        # _update_price_with_retry retries inside, so 2 products × up to 4 attempts
        # — the first attempt for product 201 dies + retries succeed; same for 202
        # to keep the test deterministic, force "first dies" then None on each
        out = weekly_reprice._run()

    assert out["updated"] == 2
    assert out["failed"] == 0
    assert up.call_count == 4  # 2 products × (1 retry + 1 success) each


# ── run() failure wrapper ───────────────────────────────────────────────────

def test_run_posts_failure_alert_and_reraises(monkeypatch):
    posted = []
    monkeypatch.setattr(weekly_reprice, "_post_webhook", lambda t: posted.append(t))
    monkeypatch.setattr(
        weekly_reprice, "_run",
        lambda: (_ for _ in ()).throw(RuntimeError("Shopify down")),
    )

    with pytest.raises(RuntimeError, match="Shopify down"):
        weekly_reprice.run()

    assert len(posted) == 1
    assert "FAILED" in posted[0]
    assert "RuntimeError" in posted[0]
    assert "Shopify down" in posted[0]


def test_run_does_not_alert_on_success(monkeypatch):
    posted = []
    monkeypatch.setattr(weekly_reprice, "_post_webhook", lambda t: posted.append(t))
    monkeypatch.setattr(weekly_reprice, "_run",
                        lambda: {"updated": 5, "failed": 0, "skipped": 0})

    out = weekly_reprice.run()
    assert out["updated"] == 5
    # _run is mocked so its internal digest call is bypassed; the wrapper
    # itself does NOT post on success — that's _run's job.
    assert posted == []
