"""Tests for the fulfillment error path: mark_error writes to Supabase
and updates state without re-queueing the failing order."""
import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Point order_monitor at a temp state file so tests don't see each other."""
    from fulfillment import order_monitor
    state_path = tmp_path / "fulfillment_state.json"
    monkeypatch.setattr(order_monitor, "_STATE", state_path)
    return state_path


def _read_state(path):
    if not path.exists():
        return {"fulfilled_order_ids": [], "pending_tracking": []}
    return json.loads(path.read_text())


def test_mark_error_appends_to_fulfilled_ids(isolated_state):
    from fulfillment.order_monitor import mark_error
    with patch("fulfillment.order_monitor._sb", return_value=None):
        mark_error(12345, "CJ rejected: out of stock")
    state = _read_state(isolated_state)
    assert "12345" in state["fulfilled_order_ids"]


def test_mark_error_idempotent(isolated_state):
    """Calling twice for the same order shouldn't duplicate the ID."""
    from fulfillment.order_monitor import mark_error
    with patch("fulfillment.order_monitor._sb", return_value=None):
        mark_error(12345, "first try")
        mark_error(12345, "second try")
    state = _read_state(isolated_state)
    assert state["fulfilled_order_ids"].count("12345") == 1


def test_mark_error_writes_supabase_row(isolated_state):
    from fulfillment.order_monitor import mark_error
    sb = MagicMock()
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        mark_error(
            12345,
            "CJ API timed out",
            order={"name": "#1042", "total_price": "29.99"},
        )

    sb.table.assert_called_with("fulfillments")
    upsert_args, upsert_kwargs = sb.table.return_value.upsert.call_args
    row = upsert_args[0]
    assert row["shopify_order_id"] == "12345"
    assert row["shopify_order_name"] == "#1042"
    assert row["shopify_order_total"] == 29.99
    assert row["status"] == "error"
    assert row["error_message"] == "CJ API timed out"
    assert upsert_kwargs.get("on_conflict") == "shopify_order_id"


def test_mark_error_truncates_long_message(isolated_state):
    from fulfillment.order_monitor import mark_error
    sb = MagicMock()
    long_msg = "x" * 1000
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        mark_error(12345, long_msg)
    row = sb.table.return_value.upsert.call_args[0][0]
    assert len(row["error_message"]) == 500


def test_mark_error_no_supabase_no_crash(isolated_state):
    """Without Supabase, mark_error still updates local state and returns cleanly."""
    from fulfillment.order_monitor import mark_error
    with patch("fulfillment.order_monitor._sb", return_value=None):
        mark_error(99, "no cloud")
    state = _read_state(isolated_state)
    assert "99" in state["fulfilled_order_ids"]
