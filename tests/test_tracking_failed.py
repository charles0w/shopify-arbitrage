"""Tests for mark_tracking_failed: writes error_message without changing status,
and returns True only on first failure (or when message changes) so the caller
can dedupe alerts across cron ticks."""
from unittest.mock import patch, MagicMock


def _patch_sb(prev_message):
    """Build a Supabase mock whose select returns a row with the given prior
    error_message. Returns (sb_mock, update_calls_list)."""
    sb = MagicMock()
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(
        data=[{"error_message": prev_message}]
    )
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value = select_chain
    return sb


def test_returns_true_on_first_failure():
    from fulfillment.order_monitor import mark_tracking_failed
    sb = _patch_sb(prev_message=None)
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        assert mark_tracking_failed("12345", "boom") is True


def test_returns_false_on_repeated_identical_failure():
    """If the same error fires again next tick, don't alert again."""
    from fulfillment.order_monitor import mark_tracking_failed
    sb = _patch_sb(prev_message="boom")
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        assert mark_tracking_failed("12345", "boom") is False


def test_returns_true_when_message_changes():
    """A different exception means a different problem — alert again."""
    from fulfillment.order_monitor import mark_tracking_failed
    sb = _patch_sb(prev_message="old error")
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        assert mark_tracking_failed("12345", "different error") is True


def test_writes_update_with_bounded_message():
    from fulfillment.order_monitor import mark_tracking_failed
    sb = _patch_sb(prev_message=None)
    long_msg = "x" * 1000
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        mark_tracking_failed("12345", long_msg)
    # Find the update().update({...}) call
    update_call = sb.table.return_value.update.call_args
    payload = update_call[0][0]
    assert len(payload["error_message"]) == 500
    # status is NOT updated — CJ order itself is fine
    assert "status" not in payload


def test_no_supabase_returns_true_for_alert():
    """Without Supabase we can't dedupe — caller should alert each time."""
    from fulfillment.order_monitor import mark_tracking_failed
    with patch("fulfillment.order_monitor._sb", return_value=None):
        assert mark_tracking_failed("12345", "boom") is True


def test_update_tracking_in_supabase_clears_error_message():
    """When push finally succeeds, the stale error_message must be cleared."""
    from fulfillment.order_monitor import update_tracking_in_supabase
    sb = MagicMock()
    with patch("fulfillment.order_monitor._sb", return_value=sb):
        update_tracking_in_supabase("12345", "1Z999", "UPS")
    payload = sb.table.return_value.update.call_args[0][0]
    assert payload["status"] == "shipped"
    assert payload["error_message"] is None
