"""Tests for the stuck-cj_pending sweep added in this PR.

A row gets stuck if mark_cj_pending succeeds but the process dies before
place_cj_order or mark_fulfilled completes. Without detection, the order
silently sits at cj_pending forever — Shopify shows paid+unfulfilled and
the duplicate-prevention guard skips it on every subsequent tick.
"""
from unittest.mock import patch, MagicMock

import pytest

from fulfillment import order_monitor


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    monkeypatch.setattr(order_monitor, "_SUPABASE_RETRY_BACKOFF_S", (0, 0, 0))


# ── find_stuck_cj_pending ───────────────────────────────────────────────────

def test_find_stuck_returns_supabase_rows():
    sb = MagicMock()
    chain = (
        sb.table.return_value.select.return_value
        .eq.return_value.is_.return_value.lt.return_value
    )
    chain.execute.return_value = MagicMock(
        data=[{"shopify_order_id": "1", "shopify_order_name": "#A", "created_at": "x"}]
    )
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        out = order_monitor.find_stuck_cj_pending(threshold_minutes=30)
    assert len(out) == 1
    assert out[0]["shopify_order_id"] == "1"


def test_find_stuck_filters_by_status_and_null_error():
    """Verify the query filters status=cj_pending AND error_message IS NULL —
    those are the dedup invariants."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.is_.return_value.lt.return_value.execute.return_value = MagicMock(data=[])
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        order_monitor.find_stuck_cj_pending()

    select = sb.table.return_value.select.return_value
    select.eq.assert_called_with("status", "cj_pending")
    select.eq.return_value.is_.assert_called_with("error_message", "null")


def test_find_stuck_no_supabase_returns_empty():
    with patch("fulfillment.order_monitor._sb", return_value=None):
        assert order_monitor.find_stuck_cj_pending() == []


# ── mark_stuck_cj_pending ───────────────────────────────────────────────────

def test_mark_stuck_writes_error_message():
    sb = MagicMock()
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        order_monitor.mark_stuck_cj_pending("999", "stuck for 30min")
    payload = sb.table.return_value.update.call_args[0][0]
    assert payload["error_message"] == "stuck for 30min"
    # status is NOT touched — the row is still cj_pending until reconciled
    assert "status" not in payload


def test_mark_stuck_truncates_long_message():
    sb = MagicMock()
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        order_monitor.mark_stuck_cj_pending("999", "x" * 1000)
    payload = sb.table.return_value.update.call_args[0][0]
    assert len(payload["error_message"]) == 500


# ── loop.sweep_stuck_cj_pending integration ─────────────────────────────────

def test_sweep_marks_and_alerts(tmp_path, monkeypatch):
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    from fulfillment import loop

    stuck_rows = [
        {"shopify_order_id": "111", "shopify_order_name": "#1001", "created_at": "x"},
        {"shopify_order_id": "222", "shopify_order_name": "#1002", "created_at": "y"},
    ]
    with patch.object(loop, "find_stuck_cj_pending", return_value=stuck_rows), \
         patch.object(loop, "mark_stuck_cj_pending") as mark_mock, \
         patch.object(loop, "_alert") as alert_mock:
        loop.sweep_stuck_cj_pending()

    assert mark_mock.call_count == 2
    assert alert_mock.call_count == 2
    # alert message includes the order name and recovery instructions
    msg = alert_mock.call_args_list[0][0][0]
    assert "#1001" in msg
    assert "remark" in msg


def test_sweep_no_stuck_rows_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    from fulfillment import loop

    with patch.object(loop, "find_stuck_cj_pending", return_value=[]), \
         patch.object(loop, "mark_stuck_cj_pending") as mark_mock, \
         patch.object(loop, "_alert") as alert_mock:
        loop.sweep_stuck_cj_pending()

    mark_mock.assert_not_called()
    alert_mock.assert_not_called()
