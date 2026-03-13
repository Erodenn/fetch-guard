"""Tests for html_sanitizer module."""

from fetch_guard.scripts import html_sanitizer


class TestSanitize:
    """Tests for html_sanitizer.sanitize()."""

    def test_clean_html_unchanged(self):
        html = "<html><body><p>Hello world</p></body></html>"
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "Hello world" in cleaned
        assert tally["hidden_elements"] == 0
        assert tally["offscreen_elements"] == 0
        assert tally["nonprinting_chars"] == 0

    def test_removes_display_none(self):
        html = '<div style="display: none">hidden</div><p>visible</p>'
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "hidden" not in cleaned
        assert "visible" in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_visibility_hidden(self):
        html = '<span style="visibility: hidden">sneaky</span><p>ok</p>'
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "sneaky" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_opacity_zero(self):
        html = '<div style="opacity: 0">transparent</div><p>solid</p>'
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "transparent" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_aria_hidden(self):
        html = '<span aria-hidden="true">screen reader only</span><p>content</p>'
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "screen reader only" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_offscreen_elements(self):
        html = '<div style="position: absolute; left: -9999px">offscreen</div><p>onscreen</p>'
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "offscreen" not in cleaned
        assert tally["offscreen_elements"] == 1

    def test_removes_noscript(self):
        html = "<noscript>Enable JavaScript</noscript><p>content</p>"
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "Enable JavaScript" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_strips_zero_width_spaces(self):
        html = "<p>hel\u200blo</p>"
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "\u200b" not in cleaned
        assert "hello" in cleaned
        assert tally["nonprinting_chars"] >= 1

    def test_strips_bom(self):
        html = "\ufeff<p>content</p>"
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "\ufeff" not in cleaned
        assert tally["nonprinting_chars"] >= 1

    def test_preserves_whitespace_chars(self):
        html = "<p>line1\nline2\ttabbed</p>"
        cleaned, _ = html_sanitizer.sanitize(html)
        assert "\n" in cleaned
        assert "\t" in cleaned

    def test_multiple_hidden_elements(self):
        html = (
            '<div style="display:none">a</div>'
            '<div style="visibility:hidden">b</div>'
            '<span aria-hidden="true">c</span>'
            "<p>visible</p>"
        )
        cleaned, tally = html_sanitizer.sanitize(html)
        assert "visible" in cleaned
        assert tally["hidden_elements"] == 3


class TestStripNonprinting:
    """Tests for html_sanitizer._strip_nonprinting()."""

    def test_empty_string(self):
        result, count = html_sanitizer._strip_nonprinting("")
        assert result == ""
        assert count == 0

    def test_no_nonprinting(self):
        result, count = html_sanitizer._strip_nonprinting("normal text")
        assert result == "normal text"
        assert count == 0

    def test_mixed_nonprinting(self):
        text = "he\u200bl\u200clo"
        result, count = html_sanitizer._strip_nonprinting(text)
        assert result == "hello"
        assert count == 2
