"""Tests for text normalization — homoglyph/confusable mapping."""

from fetch_guard.security.normalize import normalize_for_scan


class TestNormalizeForScan:
    """Tests for normalize_for_scan()."""

    def test_plain_ascii_unchanged(self):
        assert normalize_for_scan("hello world") == "hello world"

    def test_nfkc_normalization(self):
        # Fullwidth Latin letters should collapse to ASCII
        assert normalize_for_scan("\uff49\uff47\uff4e\uff4f\uff52\uff45") == "ignore"

    def test_cyrillic_a_to_latin(self):
        # Cyrillic а (U+0430) → Latin a
        assert normalize_for_scan("\u0430") == "a"

    def test_cyrillic_confusable_word(self):
        # "ignore" spelled with Cyrillic confusables: і(U+0456) g n о(U+043e) r е(U+0435)
        text = "\u0456gn\u043er\u0435"
        result = normalize_for_scan(text)
        assert result == "ignore"

    def test_greek_confusable_word(self):
        # "system" with Greek σ→s doesn't map (σ isn't in our table), but α→a works
        text = "syst\u03b5m"  # ε → e
        result = normalize_for_scan(text)
        assert result == "system"

    def test_mixed_script_injection_phrase(self):
        # "ignore previous" with mixed Cyrillic
        text = "\u0456gn\u043er\u0435 pr\u0435v\u0456\u043eus"
        result = normalize_for_scan(text)
        assert result == "ignore previous"

    def test_preserves_case(self):
        # Our patterns use IGNORECASE so we don't lowercase
        assert normalize_for_scan("HELLO") == "HELLO"

    def test_cyrillic_uppercase_mapped(self):
        # Cyrillic А (U+0410) → a
        assert normalize_for_scan("\u0410") == "a"

    def test_empty_string(self):
        assert normalize_for_scan("") == ""

    def test_non_confusable_unicode_preserved(self):
        # CJK characters should pass through unchanged
        text = "hello \u4e16\u754c"
        result = normalize_for_scan(text)
        assert "\u4e16" in result
        assert "\u754c" in result
