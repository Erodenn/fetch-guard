"""Tests for output_formatter module."""

import output_formatter


def _make_risk_result(risk="OK", matches=None):
    return {"risk": risk, "matches": matches or []}


def _make_tally(hidden=0, offscreen=0, nonprinting=0):
    return {
        "hidden_elements": hidden,
        "offscreen_elements": offscreen,
        "nonprinting_chars": nonprinting,
    }


class TestFormatOutput:
    """Tests for output_formatter.format_output()."""

    def test_contains_url(self):
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result(),
            sanitize_tally=_make_tally(),
            salted_body="<fetch-content-abc>body</fetch-content-abc>",
        )
        assert "https://example.com" in output

    def test_contains_timestamp(self):
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result(),
            sanitize_tally=_make_tally(),
            salted_body="body",
        )
        assert "2026-03-11T12:00:00Z" in output

    def test_ok_status(self):
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result("OK"),
            sanitize_tally=_make_tally(),
            salted_body="body",
        )
        assert "Status: OK" in output

    def test_injection_warning_status(self):
        matches = [{"pattern": "test", "severity": "high", "snippet": "bad stuff"}]
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result("HIGH", matches),
            sanitize_tally=_make_tally(),
            salted_body="body",
        )
        assert "INJECTION WARNING" in output
        assert "1 pattern match)" in output

    def test_plural_matches(self):
        matches = [
            {"pattern": "a", "severity": "high", "snippet": "x"},
            {"pattern": "b", "severity": "medium", "snippet": "y"},
        ]
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result("HIGH", matches),
            sanitize_tally=_make_tally(),
            salted_body="body",
        )
        assert "2 pattern matches)" in output

    def test_sanitize_tally_in_output(self):
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result(),
            sanitize_tally=_make_tally(hidden=3, offscreen=1, nonprinting=42),
            salted_body="body",
        )
        assert "3 hidden elements" in output
        assert "1 offscreen elements" in output
        assert "42 non-printing chars" in output

    def test_max_words_truncates(self):
        long_body = " ".join(f"word{i}" for i in range(100))
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result(),
            sanitize_tally=_make_tally(),
            salted_body=long_body,
            max_words=10,
        )
        assert "[Truncated at 10 words]" in output

    def test_max_words_no_truncation_when_under(self):
        short_body = "just a few words"
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result(),
            sanitize_tally=_make_tally(),
            salted_body=short_body,
            max_words=100,
        )
        assert "Truncated" not in output

    def test_injection_details_section(self):
        matches = [{"pattern": "ignore_previous", "severity": "high", "snippet": "ignore all previous"}]
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result("HIGH", matches),
            sanitize_tally=_make_tally(),
            salted_body="body",
        )
        assert "INJECTION DETAILS" in output
        assert "[HIGH] ignore_previous" in output

    def test_no_injection_details_when_clean(self):
        output = output_formatter.format_output(
            url="https://example.com",
            fetch_timestamp="2026-03-11T12:00:00Z",
            risk_result=_make_risk_result(),
            sanitize_tally=_make_tally(),
            salted_body="body",
        )
        assert "INJECTION DETAILS" not in output
