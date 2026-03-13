"""Tests for injection_patterns — validates pattern structure and basic matching."""

from fetch_guard.scripts import injection_patterns


class TestPatternRegistry:
    """Validate the PATTERNS constant structure."""

    def test_patterns_is_list(self):
        assert isinstance(injection_patterns.PATTERNS, list)
        assert len(injection_patterns.PATTERNS) > 0

    def test_each_pattern_is_3_tuple(self):
        for entry in injection_patterns.PATTERNS:
            assert len(entry) == 3, f"Pattern entry has {len(entry)} items, expected 3"

    def test_severity_values_valid(self):
        valid_severities = {"high", "medium"}
        for name, _, severity in injection_patterns.PATTERNS:
            assert severity in valid_severities, f"Pattern '{name}' has invalid severity: {severity}"

    def test_pattern_names_unique(self):
        names = [name for name, _, _ in injection_patterns.PATTERNS]
        assert len(names) == len(set(names)), "Duplicate pattern names found"

    def test_all_patterns_compilable(self):
        """Patterns are pre-compiled, so just verify they have a finditer method."""
        for name, pattern, _ in injection_patterns.PATTERNS:
            assert hasattr(pattern, "finditer"), f"Pattern '{name}' is not a compiled regex"
