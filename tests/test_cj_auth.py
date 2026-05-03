"""Tests for the auth-error detection helper used to trigger CJ token refresh."""
from unittest.mock import MagicMock

from research.aliexpress_fetcher import _is_auth_error


class _Resp:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no payload")
        return self._payload


def test_401_is_auth_error():
    assert _is_auth_error(_Resp(401)) is True


def test_403_is_auth_error():
    assert _is_auth_error(_Resp(403)) is True


def test_200_with_token_message_is_auth_error():
    assert _is_auth_error(_Resp(200, {"result": False, "message": "Access token invalid"})) is True


def test_200_with_unrelated_failure_is_not_auth_error():
    assert _is_auth_error(_Resp(200, {"result": False, "message": "Out of stock"})) is False


def test_200_success_is_not_auth_error():
    assert _is_auth_error(_Resp(200, {"result": True, "data": {}})) is False


def test_dict_directly_token_message():
    assert _is_auth_error({"result": False, "message": "auth expired"}) is True


def test_dict_directly_success():
    assert _is_auth_error({"result": True}) is False


def test_non_json_response_is_not_auth_error():
    """A 200 with no JSON shouldn't crash and shouldn't be treated as auth error."""
    assert _is_auth_error(_Resp(200)) is False
