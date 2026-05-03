"""
Generate Shopify listing copy using Claude API.
Returns: title, body_html, tags, meta_title, meta_description.
"""
import anthropic
from config.settings import ANTHROPIC_API_KEY
from listing.sanitize import sanitize_html

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """You are an expert Shopify product copywriter who writes high-converting listings.
Your copy is concise, benefit-focused, and optimised for search.
Never mention AliExpress, China, or supplier names."""

_PROMPT = """Write a Shopify product listing for this item:

Supplier title: {supplier_title}
Category / niche: {keyword}
Supplier price: ${supplier_price:.2f}
Sale price: ${sale_price:.2f}

Return ONLY valid JSON with these exact keys:
{{
  "title": "...",           // SEO-optimised, ≤ 70 chars, no ALL CAPS
  "body_html": "...",       // 3–4 benefit bullets as <ul><li> HTML, ≤ 200 words total
  "tags": ["...", "..."],   // 6–10 relevant tags, lowercase, no spaces
  "meta_title": "...",      // ≤ 60 chars
  "meta_description": "..."  // 130–160 chars
}}"""


def generate_listing(product: dict) -> dict:
    """Call Claude to generate listing copy for a scored product dict."""
    prompt = _PROMPT.format(
        supplier_title=product.get("title", ""),
        keyword=product.get("keyword", ""),
        supplier_price=product.get("supplier_price_usd", 0),
        sale_price=product.get("suggested_sale_price_usd", 0),
    )

    message = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    text = message.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    listing = json.loads(text.strip())
    listing["body_html"] = sanitize_html(listing.get("body_html", ""))
    return listing
