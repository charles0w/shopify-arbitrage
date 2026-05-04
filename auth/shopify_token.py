"""
Return the Shopify Admin API access token from the environment.

shpat_ tokens issued by custom/Dev Dashboard apps do not expire unless
manually rotated, so no refresh logic is needed.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_token() -> str:
    """Return the Shopify access token from the environment."""
    token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not token:
        raise EnvironmentError("SHOPIFY_ACCESS_TOKEN not set in environment / .env")
    return token


if __name__ == "__main__":
    token = get_token()
    print(f"Token: {token[:12]}...")
