"""Tests for the Supabase retry helper and the _load_state failure-loud
behaviour. Without these, a Supabase outage during a stateless cron tick can
duplicate CJ orders by silently dropping fulfilled_order_ids."""
from unittest.mock import patch, MagicMock

import pytest

from fulfillment import order_monitor


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Don't actually sleep during retries."""
    monkeypatch.setattr(order_monitor, "_SUPABASE_RETRY_BACKOFF_S", (0, 0, 0))


# ── _supabase_retry ─────────────────────────────────────────────────────────

def test_retry_returns_immediately_on_success():
    op = MagicMock(return_value="ok")
    assert order_monitor._supabase_retry(op, label="x") == "ok"
    assert op.call_count == 1


def test_retry_recovers_after_transient_failure():
    op = MagicMock(side_effect=[Exception("blip"), Exception("blip"), "ok"])
    assert order_monitor._supabase_retry(op, label="x") == "ok"
    assert op.call_count == 3


def test_retry_raises_after_max_attempts():
    op = MagicMock(side_effect=Exception("persistent"))
    with pytest.raises(Exception, match="persistent"):
        order_monitor._supabase_retry(op, label="x")
    assert op.call_count == 4  # 1 initial + 3 retries


# ── _load_state now fails loud on Supabase outage ───────────────────────────

def test_load_state_raises_when_supabase_down(tmp_path, monkeypatch):
    """If we can't read fulfillments from Supabase in a stateless tick,
    we MUST NOT proceed — empty fulfilled_order_ids would cause every
    paid+unfulfilled Shopify order to be re-attempted on CJ."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.side_effect = (
        Exception("supabase down")
    )
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        with pytest.raises(Exception, match="supabase down"):
            order_monitor._load_state()


def test_load_state_recovers_from_transient_supabase_failure(tmp_path, monkeypatch):
    """A flaky Supabase that succeeds on retry should not bring down the tick."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    sb = MagicMock()
    success_resp = MagicMock(data=[{"shopify_order_id": "999", "status": "shipped"}])
    sb.table.return_value.select.return_value.execute.side_effect = [
        Exception("blip"),
        success_resp,
    ]
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        state = order_monitor._load_state()
    assert "999" in state["fulfilled_order_ids"]


def test_load_state_no_supabase_returns_local_state(tmp_path, monkeypatch):
    """No Supabase configured (e.g. local dev) — _load_state must still work."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    with patch("fulfillment.order_monitor._sb", return_value=None):
        state = order_monitor._load_state()
    assert state == {"fulfilled_order_ids": [], "pending_tracking": []}


# ── Write helpers go through retry ──────────────────────────────────────────

def test_mark_fulfilled_retries_supabase_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    sb = MagicMock()
    chain = sb.table.return_value.upsert.return_value
    chain.execute.side_effect = [Exception("blip"), MagicMock()]
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        order_monitor.mark_fulfilled(123, "CJ-7", order={"name": "#A", "total_price": "10"})
    # First call failed, second succeeded — retry kicked in
    assert chain.execute.call_count == 2


def test_mark_error_propagates_after_persistent_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.side_effect = (
        Exception("supabase out")
    )
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        with pytest.raises(Exception, match="supabase out"):
            order_monitor.mark_error(123, "boom")
    # 4 attempts (1 + 3 retries)
    assert sb.table.return_value.upsert.return_value.execute.call_count == 4
