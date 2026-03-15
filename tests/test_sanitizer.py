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

    def test_removes_font_size_zero(self):
        html = '<div style="font-size: 0">inject</div><p>visible</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject" not in cleaned
        assert "visible" in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_color_transparent(self):
        html = '<span style="color: transparent">inject</span><p>ok</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_color_rgba_zero_alpha(self):
        html = '<span style="color: rgba(0,0,0,0)">inject</span><p>ok</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_height_zero_overflow_hidden(self):
        html = '<div style="height: 0; overflow: hidden">inject</div><p>ok</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_clip_rect_zero(self):
        html = '<div style="clip: rect(0,0,0,0)">inject</div><p>ok</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_transform_scale_zero(self):
        html = '<div style="transform: scale(0)">inject</div><p>ok</p>'
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_removes_template_tag(self):
        html = "<template>hidden template content</template><p>visible</p>"
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "hidden template content" not in cleaned
        assert "visible" in cleaned
        assert tally["hidden_elements"] >= 1

    def test_css_font_size_zero_class(self):
        html = """
        <html><head><style>.hidden { font-size: 0; }</style></head>
        <body><div class="hidden">inject via class</div><p>content</p></body></html>
        """
        cleaned, _soup, tally = html_sanitizer.sanitize(html)
        assert "inject via class" not in cleaned
        assert "content" in cleaned
        assert tally["hidden_elements"] >= 1


class TestColorMatchDetection:
    """Tests for color-match hidden text detection in sanitize()."""

    def _make_html(self, style):
        return f'<p style="{style}">inject</p><p>visible</p>'

    def test_hex_hex_exact_match_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:#ffffff;background-color:#ffffff")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_name_name_exact_match_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:white;background-color:white")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_rgb_rgb_match_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:rgb(0,0,0);background-color:rgb(0,0,0)")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_rgba_hex_cross_format_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:rgba(255,255,255,0.5);background-color:#ffffff")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_hex_named_cross_format_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:#000000;background-color:black")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_3digit_6digit_hex_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:#fff;background-color:#ffffff")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_8digit_hex_alpha_kept(self):
        # 8-digit hex with non-zero alpha (50%) — not caught by transparency pattern,
        # and color-match detection skips it (alpha channel present)
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:#ffffff80;background-color:#ffffff")
        )
        assert "inject" in cleaned

    def test_different_colors_kept(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:#000000;background-color:#ffffff")
        )
        assert "inject" in cleaned

    def test_only_color_no_bg_kept(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:white")
        )
        assert "inject" in cleaned

    def test_unrecognized_named_color_kept(self):
        # "thistle" is not in the curated named color table
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:thistle;background-color:thistle")
        )
        assert "inject" in cleaned

    def test_bg_color_before_color_removed(self):
        # Property order should not matter
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("background-color:white;color:white")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_tally_increments_hidden_elements(self):
        _cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:#ff0000;background-color:#ff0000")
        )
        assert tally["hidden_elements"] >= 1

    def test_display_none_takes_priority(self):
        # HIDDEN_STYLE_PATTERNS hit first; color-match branch is not reached
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("display:none;color:white;background-color:white")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_spaces_in_values_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color: white ; background-color: white")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1

    def test_black_hex_named_cross_format_removed(self):
        cleaned, _soup, tally = html_sanitizer.sanitize(
            self._make_html("color:black;background-color:#000000")
        )
        assert "inject" not in cleaned
        assert tally["hidden_elements"] >= 1


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
