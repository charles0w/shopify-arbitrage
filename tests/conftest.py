"""Set placeholder env vars before any test imports settings.py."""
import os

os.environ.setdefault("SHOPIFY_STORE_URL", "test.myshopify.com")
os.environ.setdefault("SHOPIFY_ACCESS_TOKEN", "shpat_test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("CJ_API_KEY", "cj-test")
