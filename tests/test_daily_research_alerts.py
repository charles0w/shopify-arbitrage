"""Tests for daily_research failure visibility:

  - run() failures post a webhook alert before re-raising
  - Zero-result runs trigger a distinct alert from a normal digest
  - Supabase queue_items insert retries on transient failure
"""
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Don't actually sleep during retries."""
    from pipeline import daily_research
    monkeypatch.setattr(daily_research, "_INSERT_RETRY_BACKOFF_S", (0, 0, 0))


# ── _post_failure_alert / _post_zero_result_alert ───────────────────────────

def test_failure_alert_includes_exception_class_and_traceback(monkeypatch):
    from pipeline import daily_research
    posted = []
    monkeypatch.setattr(daily_research, "_post_webhook", lambda t: posted.append(t))

    try:
        raise ValueError("pytrends timed out")
    except ValueError as e:
        daily_research._post_failure_alert("2026-05-03", e)

    assert len(posted) == 1
    msg = posted[0]
    assert "FAILED" in msg
    assert "2026-05-03" in msg
    assert "ValueError" in msg
    assert "pytrends timed out" in msg


def test_zero_result_alert_is_distinct_from_digest(monkeypatch):
    """The zero-result alert must look different enough to catch the eye —
    a 'normal' digest could also say 0, so this needs explicit warning markers."""
    from pipeline import daily_research
    posted = []
    monkeypatch.setattr(daily_research, "_post_webhook", lambda t: posted.append(t))

    daily_research._post_zero_result_alert("2026-05-03")

    assert len(posted) == 1
    msg = posted[0]
    assert ":warning:" in msg
    assert "0 products queued" in msg


# ── _insert_with_retry ──────────────────────────────────────────────────────

def test_insert_returns_immediately_on_success():
    from pipeline import daily_research
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value = "ok"
    out = daily_research._insert_with_retry(sb, [{"a": 1}])
    assert out == "ok"
    assert sb.table.return_value.insert.return_value.execute.call_count == 1


def test_insert_recovers_from_transient_failure():
    from pipeline import daily_research
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = [
        Exception("blip"),
        Exception("blip"),
        "ok",
    ]
    out = daily_research._insert_with_retry(sb, [{"a": 1}])
    assert out == "ok"
    assert sb.table.return_value.insert.return_value.execute.call_count == 3


def test_insert_raises_after_max_attempts():
    from pipeline import daily_research
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = (
        Exception("persistent")
    )
    with pytest.raises(Exception, match="persistent"):
        daily_research._insert_with_retry(sb, [{"a": 1}])
    assert sb.table.return_value.insert.return_value.execute.call_count == 4


# ── run() wraps and re-raises ───────────────────────────────────────────────

def test_run_posts_failure_alert_and_reraises(monkeypatch):
    from pipeline import daily_research

    posted = []
    monkeypatch.setattr(daily_research, "_post_webhook", lambda t: posted.append(t))
    monkeypatch.setattr(daily_research, "_run", lambda today: (_ for _ in ()).throw(
        RuntimeError("CJ down")))

    with pytest.raises(RuntimeError, match="CJ down"):
        daily_research.run()

    assert len(posted) == 1
    assert "FAILED" in posted[0]
    assert "RuntimeError" in posted[0]
    assert "CJ down" in posted[0]


def test_run_does_not_post_failure_alert_on_success(monkeypatch):
    from pipeline import daily_research

    posted = []
    monkeypatch.setattr(daily_research, "_post_webhook", lambda t: posted.append(t))
    monkeypatch.setattr(daily_research, "_run", lambda today: ["ok"])

    out = daily_research.run()
    assert out == ["ok"]
    # _run is mocked so neither digest nor failure alert fires
    assert posted == []
