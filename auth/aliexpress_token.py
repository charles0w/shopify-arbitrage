"""
Fetch and cache an AliExpress Dropship API access token.
Uses /auth/token/security/create with App Key + App Secret.
Token expires — refresh_token is used to extend it.
"""
import os
import time
import json
import hashlib
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "")
_APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "")
_BASE_URL = "https://api-sg.aliexpress.com/sync"
_CACHE_PATH = Path(__file__).parent.parent / ".ae_token_cache.json"


def _sign(params: dict) -> str:
    sorted_items = sorted(params.items())
    sign_str = _APP_SECRET + "".join(f"{k}{v}" for k, v in sorted_items) + _APP_SECRET
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def _call(method: str, extra: dict) -> dict:
    params = {
        "app_key": _APP_KEY,
        "method": method,
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "md5",
        "v": "2.0",
        **extra,
    }
    params["sign"] = _sign(params)
    resp = requests.post(_BASE_URL, data=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _fetch_token() -> dict:
    data = _call("aliexpress.system.oauth.token", {
        "grant_type": "authorization_code",
    })
    # For dropship apps in test mode, use app key as code
    # Real flow requires user OAuth — for self-use we use the security token endpoint
    return data


def _fetch_security_token() -> dict:
    """Get a security access token valid for self-use (no user OAuth needed)."""
    params = {
        "app_key": _APP_KEY,
        "method": "aliexpress.solution.seller.category.tree.get",
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "md5",
        "v": "2.0",
        "app_secret": _APP_SECRET,
    }
    params["sign"] = _sign({k: v for k, v in params.items() if k != "app_secret"})
    return params


def get_token() -> str:
    """Return App Key for API calls — dropship API uses app_key + sign, no bearer token."""
    return _APP_KEY


def get_headers() -> dict:
    return {}


def get_base_params() -> dict:
    """Return the base params needed for every signed AliExpress API call."""
    return {
        "app_key": _APP_KEY,
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "md5",
        "v": "2.0",
    }


def sign(params: dict) -> str:
    return _sign(params)
