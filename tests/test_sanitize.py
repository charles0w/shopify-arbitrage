"""Tests for listing HTML sanitization."""
from listing.sanitize import sanitize_html


def test_strips_script_tag():
    """The <script> tag is removed; its inner text becomes harmless plaintext."""
    out = sanitize_html("<p>hi</p><script>alert(1)</script>")
    assert "<script" not in out
    assert "</script>" not in out
    assert "<p>hi</p>" in out


def test_strips_event_handler_attrs():
    out = sanitize_html('<p onclick="alert(1)">hi</p>')
    assert "onclick" not in out
    assert "<p>hi</p>" in out


def test_strips_javascript_protocol():
    out = sanitize_html('<a href="javascript:alert(1)">x</a>')
    assert "javascript:" not in out


def test_keeps_safe_listing_markup():
    body = (
        "<ul>"
        "<li><strong>Premium</strong> material</li>"
        "<li>Built to last</li>"
        "</ul>"
        '<p><a href="https://example.com">Learn more</a></p>'
    )
    out = sanitize_html(body)
    assert "<ul>" in out
    assert "<strong>" in out
    assert 'href="https://example.com"' in out


def test_empty_input():
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""  # type: ignore[arg-type]


def test_strips_iframe():
    out = sanitize_html('<iframe src="https://evil.example/x"></iframe>')
    assert "iframe" not in out
    assert "evil" not in out
