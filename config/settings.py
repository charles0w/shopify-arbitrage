import os
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE_URL = os.environ["SHOPIFY_STORE_URL"]
SHOPIFY_ACCESS_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
ALIEXPRESS_APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "")
ALIEXPRESS_APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "")

# Scoring thresholds
MIN_SCORE = 0.40
MAX_QUEUE_SIZE = 10

# Markup multipliers by supplier cost tier
MARKUP = {
    5: 4.0,   # cost < $5
    15: 3.0,  # cost $5–$15
    30: 2.5,  # cost $15–$30
}
DEFAULT_MARKUP = 2.0  # cost > $30

# Niche keywords for product research
NICHES = [
    "pet accessories",
    "home organization",
    "kitchen gadgets",
    "fitness accessories",
    "car accessories",
    "beauty tools",
]

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "margin_gap": 0.40,
    "trend_velocity": 0.30,
    "review_volume": 0.15,
    "shipping_weight": 0.15,
}
