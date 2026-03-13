"""Live integration tests — hit real URLs to validate the fetch pipeline end-to-end.

Run with: pytest -m live
Exclude JS tests: pytest -m "live and not js"

These tests use soft assertions: they check structure, types, and category-level
signals but never assert specific page content (too fragile for real sites).
"""

import pytest
from fetch_guard.scripts.pipeline import FetchError, run

# ---------------------------------------------------------------------------
# Structural constants
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {
    "url",
    "fetched_at",
    "body",
    "content_type",
    "metadata",
    "links",
    "links_mode",
    "risk_level",
    "injection_matches",
    "edge_cases",
    "sanitization",
    "llms_txt_available",
    "llms_txt_replaced",
    "js_rendered",
    "js_hint",
    "retried",
    "truncated_at",
}

TIMEOUT = 30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_valid_result(result):
    """Check that a pipeline result has the expected shape and types."""
    assert isinstance(result, dict)
    missing = EXPECTED_KEYS - result.keys()
    assert not missing, f"Missing keys: {missing}"

    assert isinstance(result["url"], str)
    assert isinstance(result["fetched_at"], str)
    assert isinstance(result["body"], str)
    assert isinstance(result["content_type"], str)
    assert isinstance(result["metadata"], dict)
    assert isinstance(result["links"], (list, dict))
    assert result["links_mode"] in ("domains", "full")
    assert result["risk_level"] in ("OK", "MEDIUM", "HIGH")
    assert isinstance(result["injection_matches"], list)
    assert result["edge_cases"] is None or isinstance(result["edge_cases"], dict)
    assert isinstance(result["sanitization"], dict)
    assert isinstance(result["llms_txt_available"], bool)
    assert isinstance(result["llms_txt_replaced"], bool)
    assert isinstance(result["js_rendered"], bool)
    assert isinstance(result["js_hint"], bool)
    assert isinstance(result["retried"], bool)
    assert result["truncated_at"] is None or isinstance(result["truncated_at"], int)


def _has_playwright():
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

live = pytest.mark.live


@live
def test_basic_html():
    """Fetch a standard Wikipedia article — should return rich HTML content."""
    result = run("https://en.wikipedia.org/wiki/Python_(programming_language)", timeout=TIMEOUT)
    assert_valid_result(result)
    assert len(result["body"]) > 100, "Expected substantial body content"
    assert result["edge_cases"] is None, "Wikipedia should not trigger edge detection"


@live
def test_rich_metadata():
    """Fetch a BBC article — should extract structured metadata (JSON-LD/OG)."""
    result = run("https://www.bbc.com/news", timeout=TIMEOUT)
    assert_valid_result(result)
    meta = result["metadata"]
    populated = [v for v in meta.values() if v is not None]
    assert len(populated) >= 1, "Expected at least one metadata field populated"


@live
def test_llms_txt_replacement():
    """Fetch a root domain known to publish /llms.txt — should detect and use it.

    Uses anthropic.com which publishes /llms.txt. If the site changes or the
    preflight times out, this test will fail — update the URL accordingly.
    """
    # Try multiple known /llms.txt publishers
    for url in ("https://anthropic.com", "https://docs.anthropic.com", "https://supabase.com"):
        result = run(url, timeout=TIMEOUT)
        assert_valid_result(result)
        if result["llms_txt_available"]:
            assert result["llms_txt_replaced"] is True, "Root URL should use /llms.txt content"
            assert len(result["body"]) > 0, "/llms.txt content should be non-empty"
            return
    pytest.skip("No tested domain returned /llms.txt (may be timeout or removal)")


@live
def test_rss_feed():
    """Fetch a BBC RSS feed — should detect XML/RSS and render as markdown."""
    result = run("https://feeds.bbci.co.uk/news/rss.xml", timeout=TIMEOUT)
    assert_valid_result(result)
    assert "#" in result["body"], "RSS should be rendered with markdown headings"
    assert len(result["body"]) > 50, "RSS feed should have substantial content"


@live
def test_json_api():
    """Fetch a GitHub API endpoint — should detect JSON and format it."""
    result = run("https://api.github.com/repos/anthropics/claude-code", timeout=TIMEOUT)
    assert_valid_result(result)
    assert "```json" in result["body"], "JSON should be wrapped in a fenced code block"


@live
def test_redirect():
    """Fetch a URL that redirects — final URL should differ from input.

    Uses http://nytimes.com which redirects to https://www.nytimes.com.
    Avoids root domains with /llms.txt since that replaces the URL field.
    """
    input_url = "http://nytimes.com"
    result = run(input_url, timeout=TIMEOUT)
    assert_valid_result(result)
    assert result["url"] != input_url, "Final URL should differ from input after redirect"


@live
def test_bot_block():
    """Fetch a LinkedIn profile — should detect bot blocking (status 999 or 403)."""
    try:
        result = run("https://www.linkedin.com/in/williamhgates", timeout=TIMEOUT)
        assert_valid_result(result)
        # LinkedIn may return content with edge detection or may error
        if result["edge_cases"] is not None:
            assert result["edge_cases"]["type"] == "bot_block"
    except FetchError:
        # FetchError on bot block is also acceptable behavior
        pass


@live
def test_login_wall():
    """Fetch a GitHub settings page — should redirect to /login and detect login wall.

    Authenticated-only pages on GitHub reliably redirect to /login for
    unauthenticated requests, triggering our URL-based login wall detection.
    """
    result = run("https://github.com/settings/profile", timeout=TIMEOUT)
    assert_valid_result(result)
    assert result["edge_cases"] is not None, "Expected edge case detection"
    assert result["edge_cases"]["type"] == "login_wall"
    assert "/login" in result["url"], "Should have redirected to login URL"


@live
def test_plain_text():
    """Fetch robots.txt — should return plain text content without HTML processing."""
    result = run("https://www.google.com/robots.txt", timeout=TIMEOUT)
    assert_valid_result(result)
    assert len(result["body"]) > 0, "robots.txt should have content"
    assert "<html" not in result["body"].lower(), "Plain text should not contain HTML tags"


@live
def test_minimal_content():
    """Fetch example.com — minimal page, pipeline should still succeed."""
    result = run("https://example.com", timeout=TIMEOUT)
    assert_valid_result(result)
    # No content assertions — just checking the pipeline handles a near-empty page


@live
def test_external_links():
    """Fetch Wikipedia Python page — should extract external domain links."""
    result = run("https://en.wikipedia.org/wiki/Python_(programming_language)", timeout=TIMEOUT)
    assert_valid_result(result)
    assert isinstance(result["links"], list)
    assert len(result["links"]) > 0, "Wikipedia articles have many external links"


@live
def test_injection_scan_benign():
    """Fetch the Wikipedia article on prompt injection — injection scanner should run
    and may flag patterns that appear in the educational content."""
    result = run("https://en.wikipedia.org/wiki/Prompt_injection", timeout=TIMEOUT)
    assert_valid_result(result)
    assert result["risk_level"] in ("OK", "MEDIUM", "HIGH")
    assert isinstance(result["injection_matches"], list)


@live
@pytest.mark.js
@pytest.mark.skipif(not _has_playwright(), reason="Playwright not installed")
def test_js_rendered_static_vs_dynamic():
    """Fetch hn.algolia.com — a React CSR app where static extraction gets nothing
    but Playwright renders the full Hacker News search interface.

    Static extraction returns ~69 chars (the js_hint placeholder). JS rendering
    returns thousands of chars of actual content.
    """
    url = "https://hn.algolia.com"

    # Static fetch — expect minimal content (js_hint placeholder)
    try:
        static_result = run(url, timeout=TIMEOUT)
        assert_valid_result(static_result)
        static_len = len(static_result["body"])
        assert static_result["js_hint"] is True, "Static fetch of CSR app should set js_hint"
    except FetchError:
        static_len = 0

    # JS fetch — expect substantially more content
    try:
        js_result = run(url, timeout=60, js=True)
        assert_valid_result(js_result)
        js_len = len(js_result["body"])
        assert js_result["js_rendered"] is True
    except FetchError:
        pytest.skip("JS rendering failed — site may block headless browsers")

    assert js_len > static_len, (
        f"Expected JS ({js_len} chars) > static ({static_len} chars) for CSR app"
    )
