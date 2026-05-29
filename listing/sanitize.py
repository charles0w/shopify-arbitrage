"""
Sanitize Claude-generated listing HTML before storage / display / publish.

The body_html is produced by Claude from prompts that embed supplier-controlled
strings (product titles, keywords). A crafted supplier listing could try to
prompt-inject Claude into emitting <script> or other dangerous markup, so we
strip everything except a small allowlist of basic formatting tags.
"""
import bleach

_ALLOWED_TAGS = [
    "p", "br", "strong", "em", "b", "i", "u",
    "ul", "ol", "li",
    "h1", "h2", "h3", "h4",
    "a", "img",
    "table", "thead", "tbody", "tr", "td", "th",
    "blockquote", "code", "pre", "span", "div",
]

_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "*": ["class"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_html(html: str) -> str:
    """Return html with disallowed tags/attrs/protocols stripped."""
    if not html:
        return ""
    return bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
