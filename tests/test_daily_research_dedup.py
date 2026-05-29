"""Tests for the same-day rerun dedup added by this PR.

Without this, a manual workflow_dispatch on the same day as the morning
cron (or a cron retry) inserts a second batch of queue_items rows, often
overlapping cj_product_ids with the first batch. queue_items has no
unique constraint to stop it.
"""
from unittest.mock import MagicMock


def _build_sb_with_existing(existing_ids: list[str]):
    """Mock Supabase client whose select returns existing rows for today."""
    sb = MagicMock()
    select_chain = sb.table.return_value.select.return_value.eq.return_value
    select_chain.execute.return_value = MagicMock(
        data=[{"cj_product_id": cid} for cid in existing_ids]
    )
    return sb


def test_filter_drops_overlapping_cj_product_ids():
    from pipeline import daily_research
    sb = _build_sb_with_existing(["A", "B"])
    rows = [
        {"cj_product_id": "A", "title": "old"},
        {"cj_product_id": "B", "title": "old"},
        {"cj_product_id": "C", "title": "new"},
    ]
    out = daily_research._filter_already_in_today(sb, "2026-05-03", rows)
    assert [r["cj_product_id"] for r in out] == ["C"]


def test_filter_passes_through_when_no_existing_rows():
    from pipeline import daily_research
    sb = _build_sb_with_existing([])
    rows = [{"cj_product_id": "A"}, {"cj_product_id": "B"}]
    out = daily_research._filter_already_in_today(sb, "2026-05-03", rows)
    assert out == rows


def test_filter_returns_empty_when_all_already_present():
    from pipeline import daily_research
    sb = _build_sb_with_existing(["A", "B", "C"])
    rows = [{"cj_product_id": "A"}, {"cj_product_id": "B"}]
    out = daily_research._filter_already_in_today(sb, "2026-05-03", rows)
    assert out == []


def test_filter_handles_empty_input_rows():
    from pipeline import daily_research
    sb = _build_sb_with_existing(["A"])
    out = daily_research._filter_already_in_today(sb, "2026-05-03", [])
    assert out == []
    # Doesn't even hit Supabase when rows is empty
    sb.table.assert_not_called()


def test_filter_uses_today_in_query():
    from pipeline import daily_research
    sb = _build_sb_with_existing([])
    daily_research._filter_already_in_today(sb, "2026-12-25", [{"cj_product_id": "x"}])
    # .select("cj_product_id").eq("date", "2026-12-25")
    sb.table.return_value.select.assert_called_with("cj_product_id")
    sb.table.return_value.select.return_value.eq.assert_called_with("date", "2026-12-25")
