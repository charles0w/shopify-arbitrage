"""
One-time AliExpress OAuth flow to get an access_token.

Step 1: Run this script — it prints an authorization URL.
Step 2: Visit the URL in your browser and authorize.
Step 3: You'll be redirected to your callback URL with ?code=XXXX in the address bar.
Step 4: Copy that code and run: python -m auth.aliexpress_oauth <code>
"""
import sys
import os
import json
import time
import hashlib
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

_APP_KEY = os.environ["ALIEXPRESS_APP_KEY"]
_APP_SECRET = os.environ["ALIEXPRESS_APP_SECRET"]
_CALLBACK = "https://charles-arbitrage-store.myshopify.com"
_BASE_URL = "https://api-sg.aliexpress.com/sync"
_AUTH_URL = "https://oauth.aliexpress.com/authorize"
_AUTH_URL_ALT = "https://api-sg.aliexpress.com/oauth/authorize"
_CACHE = Path(__file__).parent.parent / ".ae_token_cache.json"


def _sign(params: dict) -> str:
    items = sorted(params.items())
    s = _APP_SECRET + "".join(f"{k}{v}" for k, v in items) + _APP_SECRET
    return hashlib.md5(s.encode()).hexdigest().upper()


def print_auth_url():
    from urllib.parse import quote
    callback = quote(_CALLBACK, safe="")
    url = (
        f"{_AUTH_URL}"
        f"?response_type=code"
        f"&force_auth=true"
        f"&redirect_uri={callback}"
        f"&client_id={_APP_KEY}"
    )
    url_alt = (
        f"{_AUTH_URL_ALT}"
        f"?response_type=code"
        f"&force_auth=true"
        f"&redirect_uri={callback}"
        f"&client_id={_APP_KEY}"
    )
    print("\nTry URL 1:")
    print(url)
    print("\nIf that doesn't work, try URL 2:")
    print(url_alt)
    print("\nAfter authorizing, copy the 'code' value from the redirect URL.")
    print("Then run:  python -m auth.aliexpress_oauth <code>\n")


def exchange_code(code: str):
    params = {
        "app_key": _APP_KEY,
        "method": "aliexpress.system.oauth.token",
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "md5",
        "v": "2.0",
        "code": code,
        "grant_type": "authorization_code",
    }
    params["sign"] = _sign(params)
    resp = requests.post(_BASE_URL, data=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2))

    token_data = data.get("aliexpress_system_oauth_token_response", {})
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        print("\n[!] No access_token in response — check the output above.")
        return

    token_data["fetched_at"] = time.time()
    with open(_CACHE, "w") as f:
        json.dump(token_data, f, indent=2)

    env_path = str(Path(__file__).parent.parent / ".env")
    set_key(env_path, "ALIEXPRESS_ACCESS_TOKEN", access_token)
    if refresh_token:
        set_key(env_path, "ALIEXPRESS_REFRESH_TOKEN", refresh_token)

    print(f"\n[OK] Token saved. Access token: {access_token[:20]}...")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_auth_url()
    else:
        exchange_code(sys.argv[1])
