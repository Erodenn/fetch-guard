"""Tests for output_formatter module."""

import json

from fetch_guard.scripts import output_formatter


def _make_result(**overrides):
    """Build a minimal pipeline result dict with sensible defaults."""
    base = {
        "url": "https://example.com",
        "fetched_at": "2026-03-11T12:00:00Z",
        "body": "raw body",
        "content_type": "html",
        "risk_level": "OK",
        "injection_matches": [],
        "sanitization": {
            "hidden_elements": 0,
            "offscreen_elements": 0,
            "nonprinting_chars": 0,
        },
        "metadata": None,
        "links": None,
        "links_mode": "domains",
        "edge_cases": None,
        "llms_txt_available": False,
        "llms_txt_replaced": False,
        "js_rendered": False,
        "js_hint": False,
        "retried": False,
        "truncated_at": None,
    }
    base.update(overrides)
    return base


_DEFAULT_SALTED_BODY = "<fetch-content-abc>body</fetch-content-abc>"


def _base_output(salted_body=_DEFAULT_SALTED_BODY, **overrides):
    return output_formatter.format_output(_make_result(**overrides), salted_body)


class TestFormatOutput:
    """Tests for output_formatter.format_output()."""

    def test_contains_url(self):
        output = _base_output()
        assert "https://example.com" in output

    def test_contains_timestamp(self):
        output = _base_output()
        assert "2026-03-11T12:00:00Z" in output

    def test_ok_status(self):
        output = _base_output()
        assert "Status: OK" in output

    def test_injection_warning_status(self):
        matches = [{"pattern": "test", "severity": "high", "snippet": "bad stuff"}]
        output = _base_output(risk_level="HIGH", injection_matches=matches)
        assert "INJECTION WARNING" in output
        assert "1 pattern match)" in output

    def test_plural_matches(self):
        matches = [
            {"pattern": "a", "severity": "high", "snippet": "x"},
            {"pattern": "b", "severity": "medium", "snippet": "y"},
        ]
        output = _base_output(risk_level="HIGH", injection_matches=matches)
        assert "2 pattern matches)" in output

    def test_sanitize_tally_in_output(self):
        tally = {"hidden_elements": 3, "offscreen_elements": 1, "nonprinting_chars": 42}
        output = _base_output(sanitization=tally)
        assert "3 hidden elements" in output
        assert "1 offscreen elements" in output
        assert "42 non-printing chars" in output

    def test_truncated_at_appends_notice(self):
        output = _base_output(truncated_at=10)
        assert "[Truncated at 10 words]" in output

    def test_no_truncation_notice_when_none(self):
        output = _base_output()
        assert "Truncated" not in output

    def test_injection_details_section(self):
        matches = [{"pattern": "ignore_previous", "severity": "high", "snippet": "ignore all previous"}]
        output = _base_output(risk_level="HIGH", injection_matches=matches)
        assert "INJECTION DETAILS" in output
        assert "[HIGH] ignore_previous" in output

    def test_no_injection_details_when_clean(self):
        output = _base_output()
        assert "INJECTION DETAILS" not in output


class TestMetadataSection:
    """Tests for metadata output section."""

    def test_metadata_section_present(self):
        output = _base_output(metadata={"title": "Test"})
        assert "--- METADATA ---" in output

    def test_metadata_json_formatted(self):
        metadata = {"title": "Test Page", "author": "Alice"}
        output = _base_output(metadata=metadata)
        start = output.index("--- METADATA ---\n") + len("--- METADATA ---\n")
        end = output.index("\n---", start)
        parsed = json.loads(output[start:end])
        assert parsed["title"] == "Test Page"
        assert parsed["author"] == "Alice"

    def test_no_metadata_section_when_none(self):
        output = _base_output()
        assert "METADATA" not in output

    def test_metadata_after_body(self):
        output = _base_output(metadata={"title": "T"})
        body_pos = output.index("fetch-content-abc")
        meta_pos = output.index("METADATA")
        assert meta_pos > body_pos


class TestLinksSection:
    """Tests for external links output section."""

    def test_domains_mode(self):
        output = _base_output(links=["example.org", "other.com"], links_mode="domains")
        assert "--- EXTERNAL LINKS ---" in output
        assert "example.org" in output
        assert "other.com" in output

    def test_full_mode(self):
        links = {
            "example.org": [{"url": "https://example.org/page", "anchor": "Link Text"}],
        }
        output = _base_output(links=links, links_mode="full")
        assert "--- EXTERNAL LINKS ---" in output
        assert "example.org:" in output
        assert "https://example.org/page" in output
        assert "(Link Text)" in output

    def test_no_links_section_when_none(self):
        output = _base_output()
        assert "EXTERNAL LINKS" not in output

    def test_no_links_section_when_empty_list(self):
        output = _base_output(links=[], links_mode="domains")
        assert "EXTERNAL LINKS" not in output

    def test_full_mode_empty_anchor(self):
        links = {
            "example.org": [{"url": "https://example.org/page", "anchor": ""}],
        }
        output = _base_output(links=links, links_mode="full")
        assert "https://example.org/page" in output
        assert "()" not in output


class TestLlmsTxtHeaders:
    """Tests for /llms.txt header lines."""

    def test_source_llms_txt_when_replaced(self):
        output = _base_output(llms_txt_replaced=True)
        assert "Source: /llms.txt" in output

    def test_llms_txt_available_note(self):
        output = _base_output(llms_txt_available=True)
        assert "/llms.txt: available" in output

    def test_no_llms_txt_note_by_default(self):
        output = _base_output()
        assert "llms.txt" not in output

    def test_replaced_takes_precedence(self):
        output = _base_output(llms_txt_available=True, llms_txt_replaced=True)
        assert "Source: /llms.txt" in output
        assert "/llms.txt: available" not in output


class TestPhase3Headers:
    """Tests for Phase 3 header fields (JS rendering, edge cases, hints)."""

    def test_js_rendered_header(self):
        output = _base_output(js_rendered=True)
        assert "Renderer: Playwright (JavaScript)" in output

    def test_no_js_rendered_by_default(self):
        output = _base_output()
        assert "Renderer" not in output

    def test_edge_type_header(self):
        output = _base_output(
            edge_cases={"type": "bot_block", "detail": "Cloudflare challenge detected"},
        )
        assert "Edge case: bot_block (Cloudflare challenge detected)" in output

    def test_no_edge_type_by_default(self):
        output = _base_output()
        assert "Edge case" not in output

    def test_retried_header(self):
        output = _base_output(retried=True)
        assert "Retried: yes (alternative User-Agent)" in output

    def test_no_retried_by_default(self):
        output = _base_output()
        assert "Retried" not in output

    def test_js_hint_header(self):
        output = _base_output(js_hint=True)
        assert "Hint: static extraction returned no content -- retry with --js" in output

    def test_no_js_hint_by_default(self):
        output = _base_output()
        assert "Hint" not in output

    def test_all_phase3_headers_together(self):
        output = _base_output(
            js_rendered=True,
            edge_cases={"type": "bot_block", "detail": "Cloudflare challenge detected"},
            retried=True,
        )
        assert "Renderer: Playwright" in output
        assert "Edge case: bot_block" in output
        assert "Retried: yes" in output

    def test_phase3_headers_before_closing_separator(self):
        output = _base_output(
            js_rendered=True,
            edge_cases={"type": "paywall", "detail": "Paywall pattern detected"},
        )
        lines = output.split("\n")
        renderer_idx = next(i for i, line in enumerate(lines) if "Renderer" in line)
        edge_idx = next(i for i, line in enumerate(lines) if "Edge case" in line)
        separator_idx = next(i for i, line in enumerate(lines) if line == "---" and i > 0)
        assert renderer_idx < separator_idx
        assert edge_idx < separator_idx


class TestSectionOrder:
    """Test that output sections appear in the correct order."""

    def test_order_body_metadata_links_injection(self):
        matches = [{"pattern": "test", "severity": "medium", "snippet": "x"}]
        output = _base_output(
            risk_level="MEDIUM",
            injection_matches=matches,
            metadata={"title": "T"},
            links=["other.com"],
            links_mode="domains",
        )
        body_pos = output.index("fetch-content-abc")
        meta_pos = output.index("METADATA")
        links_pos = output.index("EXTERNAL LINKS")
        inject_pos = output.index("INJECTION DETAILS")
        assert body_pos < meta_pos < links_pos < inject_pos
