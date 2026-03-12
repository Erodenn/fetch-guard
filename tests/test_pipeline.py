"""Tests for pipeline module."""

from unittest.mock import patch

import pytest

from pipeline import FetchError, run

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_fetch_result(
    html="<html><body><p>Hello world</p></body></html>",
    url="https://example.com",
    error=None,
):
    return {
        "status_code": 200,
        "html": html,
        "final_url": url,
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

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_returns_all_expected_keys(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        mock_sanitizer.sanitize.return_value = (
            "<p>Hello world</p>", _zero_tally(),
        )
        mock_content.extract.return_value = "Hello world"
        mock_meta.extract.return_value = _null_meta(title="Test")
        mock_links.extract_domains.return_value = ["other.com"]
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com")

        expected_keys = {
            "url", "fetched_at", "body", "metadata", "links",
            "links_mode", "risk_level", "injection_matches",
            "edge_cases", "sanitization", "llms_txt_available",
            "llms_txt_replaced", "js_rendered", "js_hint",
            "retried", "truncated_at",
        }
        assert set(result.keys()) == expected_keys

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_basic_field_values(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        tally = _zero_tally(
            hidden_elements=1, offscreen_elements=2, nonprinting_chars=3,
        )
        mock_sanitizer.sanitize.return_value = ("<p>Hello</p>", tally)
        mock_content.extract.return_value = "Hello"
        mock_meta.extract.return_value = _null_meta(title="T")
        mock_links.extract_domains.return_value = []
        mock_guard.scan.return_value = _OK_SCAN

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

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.fetch_client")
    def test_fetch_error_raises(self, mock_client, mock_llms):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result(
            error="Connection refused",
        )

        with pytest.raises(FetchError, match="Connection refused"):
            run("https://example.com")

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    def test_empty_html_raises(self, mock_client, mock_edge, mock_llms):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result(html="")
        mock_edge.detect.return_value = _mock_edge_result()

        with pytest.raises(FetchError, match="No response body"):
            run("https://example.com")

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    def test_no_content_with_js_raises(
        self, mock_sanitizer, mock_content, mock_client,
        mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        mock_sanitizer.sanitize.return_value = ("", _zero_tally())
        mock_content.extract.return_value = None

        with pytest.raises(FetchError, match="No content could be extracted"):
            run("https://example.com", js=True)


# ---------------------------------------------------------------------------
# JS hint
# ---------------------------------------------------------------------------

class TestJsHint:
    """Tests for the js_hint flag when static extraction returns nothing."""

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_js_hint_set_on_empty_static(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        mock_sanitizer.sanitize.return_value = ("", _zero_tally())
        mock_content.extract.return_value = None
        mock_meta.extract.return_value = _null_meta()
        mock_links.extract_domains.return_value = []
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["js_hint"] is True
        assert "static fetching" in result["body"]


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncation:
    """Tests for the max_words truncation."""

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_truncation_sets_field(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        mock_sanitizer.sanitize.return_value = (
            "<p>a b c d e</p>", _zero_tally(),
        )
        mock_content.extract.return_value = "one two three four five"
        mock_meta.extract.return_value = _null_meta()
        mock_links.extract_domains.return_value = []
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com", max_words=3)

        assert result["truncated_at"] == 3
        assert result["body"] == "one two three"


# ---------------------------------------------------------------------------
# Injection detection
# ---------------------------------------------------------------------------

class TestInjectionFields:
    """Tests for injection scan result mapping."""

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_injection_matches_populated(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        mock_sanitizer.sanitize.return_value = (
            "<p>test</p>", _zero_tally(),
        )
        mock_content.extract.return_value = "test content"
        mock_meta.extract.return_value = _null_meta()
        mock_links.extract_domains.return_value = []
        mock_guard.scan.return_value = {
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

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_edge_case_populated(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result(
            edge_type="paywall", detail="soft paywall detected",
        )
        mock_sanitizer.sanitize.return_value = (
            "<p>content</p>", _zero_tally(),
        )
        mock_content.extract.return_value = "content"
        mock_meta.extract.return_value = _null_meta()
        mock_links.extract_domains.return_value = []
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["edge_cases"] == {
            "type": "paywall", "detail": "soft paywall detected",
        }

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_retry_on_bot_block(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.side_effect = [
            _mock_fetch_result(),
            _mock_fetch_result(),
        ]
        mock_client.BROWSER_USER_AGENT = "Mozilla/5.0"
        mock_edge.detect.side_effect = [
            _mock_edge_result(should_retry=True),
            _mock_edge_result(),
        ]
        mock_sanitizer.sanitize.return_value = (
            "<p>content</p>", _zero_tally(),
        )
        mock_content.extract.return_value = "content"
        mock_meta.extract.return_value = _null_meta()
        mock_links.extract_domains.return_value = []
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["retried"] is True
        assert mock_client.fetch.call_count == 2


# ---------------------------------------------------------------------------
# llms.txt replacement
# ---------------------------------------------------------------------------

class TestLlmsTxt:
    """Tests for /llms.txt content replacement."""

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_llms_txt_replacement(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result(
            available=True,
            content="# LLMs.txt content",
            url="https://example.com/llms.txt",
        )
        mock_llms.is_root_url.return_value = True
        mock_sanitizer.sanitize.return_value = (
            "# LLMs.txt content", _zero_tally(),
        )
        mock_content.extract.return_value = "LLMs.txt content"
        mock_meta._null_metadata.return_value = _null_meta()
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com")

        assert result["llms_txt_available"] is True
        assert result["llms_txt_replaced"] is True
        assert result["url"] == "https://example.com/llms.txt"


# ---------------------------------------------------------------------------
# Links modes
# ---------------------------------------------------------------------------

class TestLinksMode:
    """Tests for link extraction modes."""

    @patch("pipeline.llms_txt_checker")
    @patch("pipeline.edge_detector")
    @patch("pipeline.fetch_client")
    @patch("pipeline.content_extractor")
    @patch("pipeline.html_sanitizer")
    @patch("pipeline.metadata_extractor")
    @patch("pipeline.link_extractor")
    @patch("pipeline.injection_guard")
    def test_full_links_mode(
        self, mock_guard, mock_links, mock_meta, mock_sanitizer,
        mock_content, mock_client, mock_edge, mock_llms,
    ):
        mock_llms.check.return_value = _mock_llms_result()
        mock_llms.is_root_url.return_value = False
        mock_client.fetch.return_value = _mock_fetch_result()
        mock_edge.detect.return_value = _mock_edge_result()
        mock_sanitizer.sanitize.return_value = (
            "<p>test</p>", _zero_tally(),
        )
        mock_content.extract.return_value = "test"
        mock_meta.extract.return_value = _null_meta()
        mock_links.extract_full.return_value = {
            "other.com": [{
                "url": "https://other.com/page", "anchor": "Link",
            }],
        }
        mock_guard.scan.return_value = _OK_SCAN

        result = run("https://example.com", links="full")

        assert result["links_mode"] == "full"
        mock_links.extract_full.assert_called_once()
