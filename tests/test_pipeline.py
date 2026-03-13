"""Tests for pipeline module."""

from unittest.mock import patch

import pytest
from fetch_guard.pipeline import FetchError, run

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_fetch_result(
    html="<html><body><p>Hello world</p></body></html>",
    url="https://example.com",
    error=None,
    content_type="text/html; charset=utf-8",
):
    return {
        "status_code": 200,
        "html": html,
        "final_url": url,
        "content_type": content_type,
        "error": error,
        "headers": {},
    }


def _mock_llms_result(available=False, content=None, url=None):
    return {"available": available, "content": content, "url": url}


def _mock_edge_result(edge_type=None, detail=None, should_retry=False):
    return {
        "edge_type": edge_type,
        "detail": detail,
        "should_retry": should_retry,
    }


def _zero_tally(**overrides):
    tally = {
        "hidden_elements": 0,
        "offscreen_elements": 0,
        "nonprinting_chars": 0,
    }
    tally.update(overrides)
    return tally


def _null_meta(**overrides):
    meta = {
        "title": None, "author": None, "date": None,
        "description": None, "canonical_url": None, "image": None,
    }
    meta.update(overrides)
    return meta


# Standard mock return values used by most tests
_OK_SCAN = {"risk": "OK", "matches": []}


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------

class TestRunSuccess:
    """Tests for successful pipeline runs."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_returns_all_expected_keys(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = (
            "<p>Hello world</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "Hello world"
        mock_extract_meta.return_value = _null_meta(title="Test")
        mock_extract_domains.return_value = ["other.com"]
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        expected_keys = {
            "url", "fetched_at", "body", "content_type", "metadata",
            "links", "links_mode", "risk_level", "injection_matches",
            "edge_cases", "sanitization", "llms_txt_available",
            "llms_txt_replaced", "js_rendered", "js_hint",
            "retried", "truncated_at",
        }
        assert set(result.keys()) == expected_keys

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_basic_field_values(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        tally = _zero_tally(
            hidden_elements=1, offscreen_elements=2, nonprinting_chars=3,
        )
        mock_sanitize.return_value = ("<p>Hello</p>", None, tally)
        mock_extract_content.return_value = "Hello"
        mock_extract_meta.return_value = _null_meta(title="T")
        mock_extract_domains.return_value = []
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["url"] == "https://example.com"
        assert result["body"] == "Hello"
        assert result["risk_level"] == "OK"
        assert result["injection_matches"] == []
        assert result["links_mode"] == "domains"
        assert result["js_rendered"] is False
        assert result["js_hint"] is False
        assert result["retried"] is False
        assert result["truncated_at"] is None
        assert result["edge_cases"] is None
        assert result["sanitization"] == tally


# ---------------------------------------------------------------------------
# FetchError cases
# ---------------------------------------------------------------------------

class TestRunErrors:
    """Tests for pipeline error handling."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.static_fetch")
    def test_fetch_error_raises(self, mock_static_fetch, mock_is_root, mock_check_llms):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            error="Connection refused",
        )

        with pytest.raises(FetchError, match="Connection refused"):
            run("https://example.com")

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    def test_empty_html_raises(self, mock_static_fetch, mock_detect_edges, mock_is_root, mock_check_llms):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(html="")
        mock_detect_edges.return_value = _mock_edge_result()

        with pytest.raises(FetchError, match="No response body"):
            run("https://example.com")

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.playwright_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    def test_no_content_with_js_raises(
        self, mock_sanitize, mock_extract_content, mock_playwright,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_playwright.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = ("", None, _zero_tally())
        mock_extract_content.return_value = None

        with pytest.raises(FetchError, match="No content could be extracted"):
            run("https://example.com", js=True)


# ---------------------------------------------------------------------------
# JS hint
# ---------------------------------------------------------------------------

class TestJsHint:
    """Tests for the js_hint flag when static extraction returns nothing."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_js_hint_set_on_empty_static(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = ("", None, _zero_tally())
        mock_extract_content.return_value = None
        mock_extract_meta.return_value = _null_meta()
        mock_extract_domains.return_value = []
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["js_hint"] is True
        assert "static fetching" in result["body"]


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncation:
    """Tests for the max_words truncation."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_truncation_sets_field(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = (
            "<p>a b c d e</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "one two three four five"
        mock_extract_meta.return_value = _null_meta()
        mock_extract_domains.return_value = []
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com", max_words=3)

        assert result["truncated_at"] == 3
        assert result["body"] == "one two three"


# ---------------------------------------------------------------------------
# Injection detection
# ---------------------------------------------------------------------------

class TestInjectionFields:
    """Tests for injection scan result mapping."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_injection_matches_populated(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = (
            "<p>test</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "test content"
        mock_extract_meta.return_value = _null_meta()
        mock_extract_domains.return_value = []
        mock_scan.return_value = {
            "risk": "HIGH",
            "matches": [{
                "pattern": "system_prompt_ref",
                "severity": "high",
                "snippet": "ignore instructions",
            }],
        }

        result = run("https://example.com")

        assert result["risk_level"] == "HIGH"
        assert len(result["injection_matches"]) == 1
        assert result["injection_matches"][0]["pattern"] == "system_prompt_ref"


# ---------------------------------------------------------------------------
# Edge cases and retry
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge case detection and retry logic."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_edge_case_populated(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result(
            edge_type="paywall", detail="soft paywall detected",
        )
        mock_sanitize.return_value = (
            "<p>content</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "content"
        mock_extract_meta.return_value = _null_meta()
        mock_extract_domains.return_value = []
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["edge_cases"] == {
            "type": "paywall", "detail": "soft paywall detected",
        }

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.BROWSER_USER_AGENT", "Mozilla/5.0")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_retry_on_bot_block(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.side_effect = [
            _mock_fetch_result(),
            _mock_fetch_result(),
        ]
        mock_detect_edges.side_effect = [
            _mock_edge_result(should_retry=True),
            _mock_edge_result(),
        ]
        mock_sanitize.return_value = (
            "<p>content</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "content"
        mock_extract_meta.return_value = _null_meta()
        mock_extract_domains.return_value = []
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["retried"] is True
        assert mock_static_fetch.call_count == 2


# ---------------------------------------------------------------------------
# llms.txt replacement
# ---------------------------------------------------------------------------

class TestLlmsTxt:
    """Tests for /llms.txt content replacement."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.null_metadata")
    @patch("fetch_guard.pipeline.scan")
    def test_llms_txt_replacement(
        self, mock_scan, mock_null_meta, mock_sanitize,
        mock_extract_content, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result(
            available=True,
            content="# LLMs.txt content",
            url="https://example.com/llms.txt",
        )
        mock_is_root.return_value = True
        mock_sanitize.return_value = (
            "# LLMs.txt content", None, _zero_tally(),
        )
        mock_extract_content.return_value = "LLMs.txt content"
        mock_null_meta.return_value = _null_meta()
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["llms_txt_available"] is True
        assert result["llms_txt_replaced"] is True
        assert result["url"] == "https://example.com/llms.txt"


# ---------------------------------------------------------------------------
# Links modes
# ---------------------------------------------------------------------------

class TestLinksMode:
    """Tests for link extraction modes."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_full")
    @patch("fetch_guard.pipeline.scan")
    def test_full_links_mode(
        self, mock_scan, mock_extract_full, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result()
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = (
            "<p>test</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "test"
        mock_extract_meta.return_value = _null_meta()
        mock_extract_full.return_value = {
            "other.com": [{
                "url": "https://other.com/page", "anchor": "Link",
            }],
        }
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com", links="full")

        assert result["links_mode"] == "full"
        mock_extract_full.assert_called_once()


# ---------------------------------------------------------------------------
# Content-type routing
# ---------------------------------------------------------------------------

class TestContentTypeRouting:
    """Tests for non-HTML content type detection and routing."""

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.scan")
    def test_json_content_type_returns_formatted_json(
        self, mock_scan, mock_static_fetch, mock_detect_edges,
        mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html='{"key": "value"}',
            content_type="application/json",
        )
        mock_detect_edges.return_value = _mock_edge_result()
        mock_scan.return_value = _OK_SCAN

        result = run("https://api.example.com/data")

        assert result["content_type"] == "json"
        assert "```json" in result["body"]
        assert '"key": "value"' in result["body"]
        assert result["js_hint"] is False
        assert result["sanitization"]["hidden_elements"] == 0

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.scan")
    def test_plain_text_content_type_passthrough(
        self, mock_scan, mock_static_fetch, mock_detect_edges,
        mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html="Just some plain text.",
            content_type="text/plain",
        )
        mock_detect_edges.return_value = _mock_edge_result()
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com/file.txt")

        assert result["content_type"] == "plain_text"
        assert result["body"] == "Just some plain text."

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.extract_content")
    @patch("fetch_guard.pipeline.sanitize")
    @patch("fetch_guard.pipeline.extract_metadata")
    @patch("fetch_guard.pipeline.extract_domains")
    @patch("fetch_guard.pipeline.scan")
    def test_plain_text_with_html_body_routes_to_html_pipeline(
        self, mock_scan, mock_extract_domains, mock_extract_meta,
        mock_sanitize, mock_extract_content, mock_static_fetch,
        mock_detect_edges, mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html="<!DOCTYPE html><html><body><p>Hello</p></body></html>",
            content_type="text/plain",
        )
        mock_detect_edges.return_value = _mock_edge_result()
        mock_sanitize.return_value = (
            "<p>Hello</p>", None, _zero_tally(),
        )
        mock_extract_content.return_value = "Hello"
        mock_extract_meta.return_value = _null_meta()
        mock_extract_domains.return_value = []
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com")

        # Should have gone through HTML pipeline
        assert result["content_type"] == "html"
        mock_sanitize.assert_called_once()

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    def test_binary_content_type_raises(
        self, mock_static_fetch, mock_detect_edges,
        mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html="",
            content_type="application/pdf",
        )
        mock_detect_edges.return_value = _mock_edge_result()

        with pytest.raises(FetchError, match="Binary content type"):
            run("https://example.com/file.pdf")

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.scan")
    def test_csv_content_type_returns_markdown_table(
        self, mock_scan, mock_static_fetch, mock_detect_edges,
        mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html="name,age\nAlice,30\nBob,25",
            content_type="text/csv",
        )
        mock_detect_edges.return_value = _mock_edge_result()
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com/data.csv")

        assert result["content_type"] == "csv"
        assert "| name | age |" in result["body"]
        assert "| Alice | 30 |" in result["body"]

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.scan")
    def test_non_html_truncation_works(
        self, mock_scan, mock_static_fetch, mock_detect_edges,
        mock_is_root, mock_check_llms,
    ):
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html="word1 word2 word3 word4 word5",
            content_type="text/plain",
        )
        mock_detect_edges.return_value = _mock_edge_result()
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com/file.txt", max_words=3)

        assert result["truncated_at"] == 3
        assert result["body"] == "word1 word2 word3"

    @patch("fetch_guard.pipeline.check_llms_txt")
    @patch("fetch_guard.pipeline.is_root_url")
    @patch("fetch_guard.pipeline.detect_edges")
    @patch("fetch_guard.pipeline.static_fetch")
    @patch("fetch_guard.pipeline.scan")
    def test_xml_rss_content_type_renders_feed(
        self, mock_scan, mock_static_fetch, mock_detect_edges,
        mock_is_root, mock_check_llms,
    ):
        rss = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <title>Feed</title>
            <item>
              <title>Post</title>
              <link>https://example.com/1</link>
            </item>
          </channel>
        </rss>"""
        mock_check_llms.return_value = _mock_llms_result()
        mock_is_root.return_value = False
        mock_static_fetch.return_value = _mock_fetch_result(
            html=rss,
            content_type="application/rss+xml",
        )
        mock_detect_edges.return_value = _mock_edge_result()
        mock_scan.return_value = _OK_SCAN

        result = run("https://example.com/feed.xml")

        assert result["content_type"] == "xml"
        assert "# Feed" in result["body"]
        assert "[Post](https://example.com/1)" in result["body"]
