"""
Fetch and cache a Shopify access token via client credentials grant.
Tokens expire after 24 hours — call get_token() before each API session.
"""
import os
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

_STORE = os.environ["SHOPIFY_STORE_URL"]
_CLIENT_ID = os.environ["SHOPIFY_CLIENT_ID"]
_CLIENT_SECRET = os.environ["SHOPIFY_CLIENT_SECRET"]
_ENV_PATH = Path(__file__).parent.parent / ".env"
_CACHE_PATH = Path(__file__).parent.parent / ".token_cache.json"

_TOKEN_URL = f"https://{_STORE}/admin/oauth/access_token"


def _fetch_token() -> dict:
    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    data["fetched_at"] = time.time()
    return data


def get_token() -> str:
    """Return a valid access token, refreshing if expired or missing."""
    if _CACHE_PATH.exists():
        with open(_CACHE_PATH) as f:
            cached = json.load(f)
        age = time.time() - cached.get("fetched_at", 0)
        expires_in = cached.get("expires_in", 0)
        if age < expires_in - 300:  # 5-min buffer
            return cached["access_token"]

    print("[shopify_token] Fetching new access token...")
    data = _fetch_token()
    with open(_CACHE_PATH, "w") as f:
        json.dump(data, f)

    # Also write to .env so other tools can use it
    set_key(str(_ENV_PATH), "SHOPIFY_ACCESS_TOKEN", data["access_token"])
    print(f"[shopify_token] Token valid for {data.get('expires_in', '?')}s")
    return data["access_token"]


if __name__ == "__main__":
    token = get_token()
    print(f"Token: {token[:20]}...")
