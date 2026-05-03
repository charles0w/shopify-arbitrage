"""Tests for fulfill_new_orders' new skip-reason tracking — orders with no
eligible line items now trigger mark_error so they surface in the dashboard
instead of vanishing into stdout."""
import json
from unittest.mock import patch


def test_order_with_no_supplier_url_calls_mark_error(tmp_path, monkeypatch):
    """An order whose product is missing the arbitrage.supplier_url metafield
    should produce a mark_error row, not be silently skipped."""
    from fulfillment import order_monitor
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")

    from fulfillment import loop

    fake_order = {
        "id": 555,
        "name": "#1042",
        "total_price": "29.99",
        "shipping_address": {"country_code": "US"},
        "line_items": [{"title": "Mystery Product", "product_id": 999, "quantity": 1}],
    }

    with patch.object(loop, "get_new_orders", return_value=[fake_order]), \
         patch.object(loop, "get_product_metafields", return_value={}), \
         patch.object(loop, "mark_error") as mark_error_mock, \
         patch.object(loop, "place_cj_order") as place_mock, \
         patch.object(loop, "_alert"):
        loop.fulfill_new_orders()

    place_mock.assert_not_called()
    mark_error_mock.assert_called_once()
    args, kwargs = mark_error_mock.call_args
    assert args[0] == 555
    assert "supplier_url" in args[1]
    assert "Mystery Product" in args[1]


def test_order_with_no_cj_variants_marks_error(tmp_path, monkeypatch):
    from fulfillment import order_monitor
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")

    from fulfillment import loop

    fake_order = {
        "id": 777,
        "name": "#1099",
        "total_price": "12.50",
        "shipping_address": {"country_code": "US"},
        "line_items": [{"title": "Delisted Item", "product_id": 1, "quantity": 1}],
    }

    with patch.object(loop, "get_new_orders", return_value=[fake_order]), \
         patch.object(loop, "get_product_metafields", return_value={
             "arbitrage.supplier_url": "https://cjdropshipping.com/product/-p-12345.html"
         }), \
         patch.object(loop, "get_cj_variants", return_value=[]), \
         patch.object(loop, "mark_error") as mark_error_mock, \
         patch.object(loop, "place_cj_order") as place_mock, \
         patch.object(loop, "_alert"):
        loop.fulfill_new_orders()

    place_mock.assert_not_called()
    mark_error_mock.assert_called_once()
    assert "no CJ variants" in mark_error_mock.call_args[0][1]


def test_alert_is_posted_for_skipped_order(tmp_path, monkeypatch):
    from fulfillment import order_monitor
    monkeypatch.setattr(order_monitor, "_STATE", tmp_path / "state.json")

    from fulfillment import loop

    fake_order = {
        "id": 1,
        "name": "#1",
        "total_price": "10",
        "line_items": [{"title": "X", "product_id": 1}],
    }

    with patch.object(loop, "get_new_orders", return_value=[fake_order]), \
         patch.object(loop, "get_product_metafields", return_value={}), \
         patch.object(loop, "mark_error"), \
         patch.object(loop, "_alert") as alert_mock:
        loop.fulfill_new_orders()

    alert_mock.assert_called_once()
    assert "#1" in alert_mock.call_args[0][0]
