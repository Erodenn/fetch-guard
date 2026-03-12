"""Tests for output_formatter module."""

import json

import output_formatter


def _make_risk_result(risk="OK", matches=None):
    return {"risk": risk, "matches": matches or []}


def _make_tally(hidden=0, offscreen=0, nonprinting=0):
    return {
        "hidden_elements": hidden,
        "offscreen_elements": offscreen,
        "nonprinting_chars": nonprinting,
    }


def _make_metadata(**kwargs):
    base = {
        "title": None, "author": None, "date": None,
        "description": None, "canonical_url": None, "image": None,
    }
    base.update(kwargs)
    return base


def _base_output(**kwargs):
    defaults = {
        "url": "https://example.com",
        "fetch_timestamp": "2026-03-11T12:00:00Z",
        "risk_result": _make_risk_result(),
        "sanitize_tally": _make_tally(),
        "salted_body": "<fetch-content-abc>body</fetch-content-abc>",
    }
    defaults.update(kwargs)
    return output_formatter.format_output(**defaults)


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
        output = _base_output(risk_result=_make_risk_result("HIGH", matches))
        assert "INJECTION WARNING" in output
        assert "1 pattern match)" in output

    def test_plural_matches(self):
        matches = [
            {"pattern": "a", "severity": "high", "snippet": "x"},
            {"pattern": "b", "severity": "medium", "snippet": "y"},
        ]
        output = _base_output(risk_result=_make_risk_result("HIGH", matches))
        assert "2 pattern matches)" in output

    def test_sanitize_tally_in_output(self):
        output = _base_output(sanitize_tally=_make_tally(hidden=3, offscreen=1, nonprinting=42))
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
        output = _base_output(risk_result=_make_risk_result("HIGH", matches))
        assert "INJECTION DETAILS" in output
        assert "[HIGH] ignore_previous" in output

    def test_no_injection_details_when_clean(self):
        output = _base_output()
        assert "INJECTION DETAILS" not in output


class TestMetadataSection:
    """Tests for metadata output section."""

    def test_metadata_section_present(self):
        metadata = _make_metadata(title="Test")
        output = _base_output(metadata=metadata)
        assert "--- METADATA ---" in output

    def test_metadata_json_formatted(self):
        metadata = _make_metadata(title="Test Page", author="Alice")
        output = _base_output(metadata=metadata)
        # Extract the JSON block
        start = output.index("--- METADATA ---\n") + len("--- METADATA ---\n")
        end = output.index("\n---", start)
        parsed = json.loads(output[start:end])
        assert parsed["title"] == "Test Page"
        assert parsed["author"] == "Alice"

    def test_no_metadata_section_when_none(self):
        output = _base_output()
        assert "METADATA" not in output

    def test_metadata_after_body(self):
        metadata = _make_metadata(title="T")
        output = _base_output(metadata=metadata)
        body_pos = output.index("fetch-content-abc")
        meta_pos = output.index("METADATA")
        assert meta_pos > body_pos


class TestLinksSection:
    """Tests for external links output section."""

    def test_domains_mode(self):
        links = ["example.org", "other.com"]
        output = _base_output(links=links, links_mode="domains")
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
        # No anchor text parentheses when empty
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


class TestSectionOrder:
    """Test that output sections appear in the correct order."""

    def test_order_body_metadata_links_injection(self):
        matches = [{"pattern": "test", "severity": "medium", "snippet": "x"}]
        metadata = _make_metadata(title="T")
        links = ["other.com"]
        output = _base_output(
            risk_result=_make_risk_result("MEDIUM", matches),
            metadata=metadata,
            links=links,
            links_mode="domains",
        )
        body_pos = output.index("fetch-content-abc")
        meta_pos = output.index("METADATA")
        links_pos = output.index("EXTERNAL LINKS")
        inject_pos = output.index("INJECTION DETAILS")
        assert body_pos < meta_pos < links_pos < inject_pos
