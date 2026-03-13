"""Tests for html_sanitizer module."""

from fetch_guard.security import sanitizer as html_sanitizer


class TestSanitize:
    """Tests for html_sanitizer.sanitize()."""

    def test_clean_html_unchanged(self):
        html = "<html><body><p>Hello world</p></body></html>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "Hello world" in cleaned
        assert tally["hidden_elements"] == 0
        assert tally["offscreen_elements"] == 0
        assert tally["nonprinting_chars"] == 0

    def test_removes_display_none(self):
        html = '<div style="display: none">hidden</div><p>visible</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "hidden" not in cleaned
        assert "visible" in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_visibility_hidden(self):
        html = '<span style="visibility: hidden">sneaky</span><p>ok</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "sneaky" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_opacity_zero(self):
        html = '<div style="opacity: 0">transparent</div><p>solid</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "transparent" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_aria_hidden(self):
        html = '<span aria-hidden="true">screen reader only</span><p>content</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "screen reader only" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_removes_offscreen_elements(self):
        html = '<div style="position: absolute; left: -9999px">offscreen</div><p>onscreen</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "offscreen" not in cleaned
        assert tally["offscreen_elements"] == 1

    def test_removes_noscript(self):
        html = "<noscript>Enable JavaScript</noscript><p>content</p>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "Enable JavaScript" not in cleaned
        assert tally["hidden_elements"] == 1

    def test_strips_zero_width_spaces(self):
        html = "<p>hel\u200blo</p>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "\u200b" not in cleaned
        assert "hello" in cleaned
        assert tally["nonprinting_chars"] >= 1

    def test_strips_bom(self):
        html = "\ufeff<p>content</p>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "\ufeff" not in cleaned
        assert tally["nonprinting_chars"] >= 1

    def test_preserves_whitespace_chars(self):
        html = "<p>line1\nline2\ttabbed</p>"
        cleaned, _, _ = html_sanitizer.sanitize(html)
        assert "\n" in cleaned
        assert "\t" in cleaned

    def test_multiple_hidden_elements(self):
        html = (
            '<div style="display:none">a</div>'
            '<div style="visibility:hidden">b</div>'
            '<span aria-hidden="true">c</span>'
            "<p>visible</p>"
        )
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "visible" in cleaned
        assert tally["hidden_elements"] == 3


    def test_strips_bidi_isolates(self):
        html = "<p>he\u2066ll\u2067o\u2069</p>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "\u2066" not in cleaned
        assert "\u2067" not in cleaned
        assert "\u2069" not in cleaned
        assert tally["nonprinting_chars"] >= 3

    def test_strips_unicode_tags(self):
        html = "<p>he\U000E0001ll\U000E0020o\U000E007F</p>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "\U000E0001" not in cleaned
        assert "\U000E0020" not in cleaned
        assert "\U000E007F" not in cleaned
        assert tally["nonprinting_chars"] >= 3

    def test_removes_css_class_hidden(self):
        html = """
        <html><head><style>.hidden { display: none; }</style></head>
        <body><div class="hidden">secret injection</div><p>visible</p></body></html>
        """
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "secret injection" not in cleaned
        assert "visible" in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_css_id_hidden(self):
        html = """
        <html><head><style>#sneaky { visibility: hidden; }</style></head>
        <body><div id="sneaky">hidden text</div><p>ok</p></body></html>
        """
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "hidden text" not in cleaned
        assert "ok" in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_css_opacity_zero_class(self):
        html = """
        <html><head><style>.transparent { opacity: 0; }</style></head>
        <body><span class="transparent">invisible</span><p>content</p></body></html>
        """
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "invisible" not in cleaned
        assert "content" in cleaned

    def test_css_hidden_preserves_visible_elements(self):
        html = """
        <html><head><style>.bad { display: none; } .good { color: red; }</style></head>
        <body><div class="bad">hidden</div><div class="good">visible</div></body></html>
        """
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "hidden" not in cleaned
        assert "visible" in cleaned

    def test_css_hidden_multiple_selectors(self):
        html = """
        <html><head><style>.a, .b { display: none; }</style></head>
        <body><div class="a">first-hidden</div><div class="b">second-hidden</div><p>three</p></body></html>
        """
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "first-hidden" not in cleaned
        assert "second-hidden" not in cleaned
        assert "three" in cleaned
        assert tally["hidden_elements"] >= 2


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
