"""Tests for the 5xx/network retry helper and the new shipping-raises behavior."""
from unittest.mock import patch, MagicMock

import pytest
import requests

from fulfillment import cj_fulfiller


# ── _post_with_retry ────────────────────────────────────────────────────────

def test_retry_returns_immediately_on_2xx(monkeypatch):
    monkeypatch.setattr(cj_fulfiller, "_RETRY_BACKOFF_S", (0, 0, 0))
    resp_ok = MagicMock(status_code=200)
    with patch("fulfillment.cj_fulfiller.requests.post", return_value=resp_ok) as post:
        out = cj_fulfiller._post_with_retry("u", headers={}, json={})
    assert out is resp_ok
    assert post.call_count == 1


def test_retry_recovers_after_transient_503(monkeypatch):
    """503, 503, 200 → returns the 200 after two backoffs."""
    monkeypatch.setattr(cj_fulfiller, "_RETRY_BACKOFF_S", (0, 0, 0))
    bad = MagicMock(status_code=503)
    good = MagicMock(status_code=200)
    with patch(
        "fulfillment.cj_fulfiller.requests.post",
        side_effect=[bad, bad, good],
    ) as post:
        out = cj_fulfiller._post_with_retry("u", headers={}, json={})
    assert out is good
    assert post.call_count == 3


def test_retry_returns_4xx_without_retrying(monkeypatch):
    """4xx is the caller's problem (auth, validation) — no retry."""
    monkeypatch.setattr(cj_fulfiller, "_RETRY_BACKOFF_S", (0, 0, 0))
    resp_401 = MagicMock(status_code=401)
    with patch("fulfillment.cj_fulfiller.requests.post", return_value=resp_401) as post:
        out = cj_fulfiller._post_with_retry("u", headers={}, json={})
    assert out is resp_401
    assert post.call_count == 1


def test_retry_gives_up_after_max_attempts(monkeypatch):
    """Persistent 503 returns the last response (caller will raise_for_status)."""
    monkeypatch.setattr(cj_fulfiller, "_RETRY_BACKOFF_S", (0, 0, 0))
    bad = MagicMock(status_code=503)
    with patch("fulfillment.cj_fulfiller.requests.post", return_value=bad) as post:
        out = cj_fulfiller._post_with_retry("u", headers={}, json={})
    assert out is bad
    assert post.call_count == 4  # 1 initial + 3 retries


def test_retry_raises_after_persistent_network_error(monkeypatch):
    monkeypatch.setattr(cj_fulfiller, "_RETRY_BACKOFF_S", (0, 0, 0))
    err = requests.ConnectionError("nope")
    with patch("fulfillment.cj_fulfiller.requests.post", side_effect=err) as post:
        with pytest.raises(requests.ConnectionError):
            cj_fulfiller._post_with_retry("u", headers={}, json={})
    assert post.call_count == 4


# ── get_cheapest_shipping now raises ────────────────────────────────────────

def test_shipping_raises_on_empty_options():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"data": []}
    resp.raise_for_status = MagicMock()
    with patch("fulfillment.cj_fulfiller.requests.post", return_value=resp), \
         patch("fulfillment.cj_fulfiller._headers", return_value={}):
        with pytest.raises(RuntimeError, match="no shipping methods"):
            cj_fulfiller.get_cheapest_shipping("vid123", "US")


def test_shipping_returns_cheapest_when_options_present():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "data": [
            {"logisticName": "Express", "logisticPrice": "20.00"},
            {"logisticName": "CJPacket", "logisticPrice": "5.00"},
            {"logisticName": "Standard", "logisticPrice": "10.00"},
        ]
    }
    resp.raise_for_status = MagicMock()
    with patch("fulfillment.cj_fulfiller.requests.post", return_value=resp), \
         patch("fulfillment.cj_fulfiller._headers", return_value={}):
        assert cj_fulfiller.get_cheapest_shipping("vid123", "US") == "CJPacket"


def test_shipping_raises_on_4xx():
    resp = MagicMock(status_code=400)
    resp.raise_for_status.side_effect = requests.HTTPError("bad request")
    with patch("fulfillment.cj_fulfiller.requests.post", return_value=resp), \
         patch("fulfillment.cj_fulfiller._headers", return_value={}):
        with pytest.raises(requests.HTTPError):
            cj_fulfiller.get_cheapest_shipping("vid123", "US")
