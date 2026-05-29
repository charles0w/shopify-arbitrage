"""Tests for mark_cj_pending and the ordering guarantee that
mark_cj_pending runs BEFORE place_cj_order — i.e. if Supabase is down,
we never reach place_cj_order and avoid risking a duplicate CJ order."""
from unittest.mock import patch, MagicMock, call

import pytest

from fulfillment import order_monitor


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    monkeypatch.setattr(order_monitor, "_SUPABASE_RETRY_BACKOFF_S", (0, 0, 0))


def test_mark_cj_pending_writes_row(tmp_path, monkeypatch):
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    sb = MagicMock()
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        order_monitor.mark_cj_pending(
            42,
            order={"name": "#100", "total_price": "19.99"},
        )
    args, kwargs = sb.table.return_value.upsert.call_args
    row = args[0]
    assert row["shopify_order_id"] == "42"
    assert row["shopify_order_name"] == "#100"
    assert row["status"] == "cj_pending"
    assert kwargs["on_conflict"] == "shopify_order_id"


def test_mark_cj_pending_adds_to_local_fulfilled_ids(tmp_path, monkeypatch):
    """Long-running processes (loop without --once) should not double-process
    an order between mark_cj_pending and mark_fulfilled."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    with patch("fulfillment.order_monitor._sb", return_value=None):
        order_monitor.mark_cj_pending(42)
    state = order_monitor._load_state()
    assert "42" in state["fulfilled_order_ids"]


def test_mark_cj_pending_propagates_supabase_failure(tmp_path, monkeypatch):
    """If Supabase is down, mark_cj_pending must raise so the caller aborts
    BEFORE place_cj_order — preventing the very duplicate this guard exists for."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.side_effect = (
        Exception("supabase out")
    )
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        with pytest.raises(Exception, match="supabase out"):
            order_monitor.mark_cj_pending(42)


def test_loop_aborts_before_cj_when_pending_write_fails(tmp_path, monkeypatch):
    """If mark_cj_pending raises, place_cj_order MUST NOT be called.
    This is the central safety property of this PR."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    from fulfillment import loop

    fake_order = {
        "id": 42,
        "name": "#100",
        "total_price": "19.99",
        "shipping_address": {"country_code": "US"},
        "line_items": [{"title": "X", "product_id": 1, "quantity": 1}],
    }

    def boom(*_a, **_kw):
        raise Exception("supabase down")

    with patch.object(loop, "get_new_orders", return_value=[fake_order]), \
         patch.object(loop, "get_product_metafields", return_value={
             "arbitrage.supplier_url": "https://cjdropshipping.com/product/-p-1.html"
         }), \
         patch.object(loop, "get_cj_variants", return_value=[{"vid": "v1"}]), \
         patch.object(loop, "get_cheapest_shipping", return_value="CJPacket"), \
         patch.object(loop, "mark_cj_pending", side_effect=boom), \
         patch.object(loop, "place_cj_order") as place_mock, \
         patch.object(loop, "mark_fulfilled") as mark_fulfilled_mock, \
         patch.object(loop, "_alert") as alert_mock:
        loop.fulfill_new_orders()

    place_mock.assert_not_called()
    mark_fulfilled_mock.assert_not_called()
    alert_mock.assert_called_once()
    assert "Supabase" in alert_mock.call_args[0][0]


def test_loop_calls_pending_before_place(tmp_path, monkeypatch):
    """Order of operations: mark_cj_pending → place_cj_order → mark_fulfilled."""
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")
    from fulfillment import loop

    fake_order = {
        "id": 7,
        "name": "#7",
        "total_price": "5",
        "shipping_address": {"country_code": "US"},
        "line_items": [{"title": "X", "product_id": 1, "quantity": 1}],
    }

    call_order = []
    with patch.object(loop, "get_new_orders", return_value=[fake_order]), \
         patch.object(loop, "get_product_metafields", return_value={
             "arbitrage.supplier_url": "https://cjdropshipping.com/product/-p-1.html"
         }), \
         patch.object(loop, "get_cj_variants", return_value=[{"vid": "v1"}]), \
         patch.object(loop, "get_cheapest_shipping", return_value="CJPacket"), \
         patch.object(loop, "mark_cj_pending", side_effect=lambda *a, **k: call_order.append("pending")), \
         patch.object(loop, "place_cj_order", side_effect=lambda *a, **k: call_order.append("place") or "CJ-X"), \
         patch.object(loop, "mark_fulfilled", side_effect=lambda *a, **k: call_order.append("fulfilled")), \
         patch.object(loop, "_alert"):
        loop.fulfill_new_orders()

    assert call_order == ["pending", "place", "fulfilled"]
