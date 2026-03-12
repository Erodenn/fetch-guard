"""Tests for link_extractor module."""

import link_extractor

SAMPLE_HTML = """
<html><body>
<a href="https://external.com/page1">External One</a>
<a href="https://external.com/page2">External Two</a>
<a href="https://other.org/about">Other Site</a>
<a href="https://example.com/internal">Internal Link</a>
<a href="/relative">Relative Link</a>
<a href="mailto:test@example.com">Email</a>
<a href="javascript:void(0)">JS Link</a>
</body></html>
"""

SOURCE_URL = "https://example.com/article"


class TestExtractDomains:
    """Tests for link_extractor.extract_domains()."""

    def test_returns_unique_sorted_domains(self):
        result = link_extractor.extract_domains(SAMPLE_HTML, SOURCE_URL)
        assert result == ["external.com", "other.org"]

    def test_excludes_same_domain(self):
        result = link_extractor.extract_domains(SAMPLE_HTML, SOURCE_URL)
        assert "example.com" not in result

    def test_excludes_relative_links(self):
        result = link_extractor.extract_domains(SAMPLE_HTML, SOURCE_URL)
        assert all("/" not in d for d in result)

    def test_excludes_non_http_schemes(self):
        result = link_extractor.extract_domains(SAMPLE_HTML, SOURCE_URL)
        assert "test@example.com" not in result

    def test_empty_html(self):
        result = link_extractor.extract_domains("", SOURCE_URL)
        assert result == []

    def test_no_external_links(self):
        html = '<a href="https://example.com/page">Same domain</a>'
        result = link_extractor.extract_domains(html, SOURCE_URL)
        assert result == []


class TestExtractFull:
    """Tests for link_extractor.extract_full()."""

    def test_groups_by_domain(self):
        result = link_extractor.extract_full(SAMPLE_HTML, SOURCE_URL)
        assert "external.com" in result
        assert "other.org" in result
        assert len(result["external.com"]) == 2
        assert len(result["other.org"]) == 1

    def test_preserves_anchor_text(self):
        result = link_extractor.extract_full(SAMPLE_HTML, SOURCE_URL)
        anchors = [link["anchor"] for link in result["external.com"]]
        assert "External One" in anchors
        assert "External Two" in anchors

    def test_preserves_urls(self):
        result = link_extractor.extract_full(SAMPLE_HTML, SOURCE_URL)
        urls = [link["url"] for link in result["external.com"]]
        assert "https://external.com/page1" in urls

    def test_domains_sorted(self):
        result = link_extractor.extract_full(SAMPLE_HTML, SOURCE_URL)
        keys = list(result.keys())
        assert keys == sorted(keys)

    def test_empty_anchor(self):
        html = '<a href="https://other.com/page"></a>'
        result = link_extractor.extract_full(html, SOURCE_URL)
        assert result["other.com"][0]["anchor"] == ""

    def test_excludes_internal(self):
        result = link_extractor.extract_full(SAMPLE_HTML, SOURCE_URL)
        assert "example.com" not in result

    def test_empty_html(self):
        result = link_extractor.extract_full("", SOURCE_URL)
        assert result == {}

    def test_case_insensitive_domain_match(self):
        html = '<a href="https://Example.COM/page">Link</a>'
        result = link_extractor.extract_domains(html, "https://example.com")
        assert result == []
