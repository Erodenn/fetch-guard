"""Catalog-driven live integration tests.

Each YAML file in tests/catalogs/ defines a list of URL entries with optional assertions.
A single parametrized test evaluates every entry — no per-URL test functions needed.

Run with: pytest -m live
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fetch_guard.pipeline import FetchError, run

# ---------------------------------------------------------------------------
# Structural constants (shared with assert_valid_result)
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {
    "url",
    "fetched_at",
    "body",
    "content_type",
    "metadata",
    "links",
    "links_mode",
    "risk_level",
    "injection_matches",
    "edge_cases",
    "sanitization",
    "llms_txt_available",
    "llms_txt_replaced",
    "js_rendered",
    "js_hint",
    "retried",
    "truncated_at",
}

CATALOGS_DIR = Path(__file__).parent / "catalogs"

DEFAULT_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_valid_result(result: dict) -> None:
    """Check that a pipeline result has the expected shape and types."""
    assert isinstance(result, dict)
    missing = EXPECTED_KEYS - result.keys()
    assert not missing, f"Missing keys: {missing}"

    assert isinstance(result["url"], str)
    assert isinstance(result["fetched_at"], str)
    assert isinstance(result["body"], str)
    assert isinstance(result["content_type"], str)
    assert isinstance(result["metadata"], dict)
    assert isinstance(result["links"], (list, dict))
    assert result["links_mode"] in ("domains", "full")
    assert result["risk_level"] in ("OK", "MEDIUM", "HIGH")
    assert isinstance(result["injection_matches"], list)
    assert result["edge_cases"] is None or isinstance(result["edge_cases"], dict)
    assert isinstance(result["sanitization"], dict)
    assert isinstance(result["llms_txt_available"], bool)
    assert isinstance(result["llms_txt_replaced"], bool)
    assert isinstance(result["js_rendered"], bool)
    assert isinstance(result["js_hint"], bool)
    assert isinstance(result["retried"], bool)
    assert result["truncated_at"] is None or isinstance(result["truncated_at"], int)


def _resolve_field(result: dict, key: str) -> Any:
    """Traverse a dot-notation key path into the result dict.

    Raises KeyError with the full key path if an intermediate value is None
    or a segment is missing.
    """
    parts = key.split(".")
    current = result
    for i, part in enumerate(parts):
        if current is None:
            traversed = ".".join(parts[:i])
            raise KeyError(f"Cannot traverse '{key}': '{traversed}' is None")
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"Key not found: '{key}' (missing segment '{part}')")
        current = current[part]
    return current


def _load_entries() -> list[pytest.param]:
    """Load all catalog YAML files and return a flat list of pytest.param objects."""
    params = []
    for catalog_path in sorted(CATALOGS_DIR.glob("*.yaml")):
        stem = catalog_path.stem
        entries = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or []
        for entry in entries:
            test_id = f"{stem}/{entry['description']}"
            params.append(pytest.param(entry, id=test_id))
    return params


# ---------------------------------------------------------------------------
# Parametrized live test
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.parametrize("entry", _load_entries())
def test_catalog_entry(entry: dict) -> None:
    url = entry["url"]
    timeout = entry.get("timeout", DEFAULT_TIMEOUT)
    max_words = entry.get("max_words")
    allow_fetch_error = entry.get("allow_fetch_error", False)
    assertions = entry.get("assertions") or {}

    try:
        result = run(url, timeout=timeout, max_words=max_words)
    except FetchError:
        if allow_fetch_error:
            return
        raise

    assert_valid_result(result)

    if "min_body_length" in assertions:
        min_len = assertions["min_body_length"]
        assert len(result["body"]) >= min_len, (
            f"body length {len(result['body'])} < expected minimum {min_len}"
        )

    if "injection_match_count_min" in assertions:
        min_count = assertions["injection_match_count_min"]
        actual = len(result["injection_matches"])
        assert actual >= min_count, (
            f"injection_matches count {actual} < expected minimum {min_count}"
        )

    if "links_count_min" in assertions:
        min_count = assertions["links_count_min"]
        links = result["links"]
        actual = len(links) if isinstance(links, list) else len(links)
        assert actual >= min_count, (
            f"links count {actual} < expected minimum {min_count}"
        )

    if assertions.get("url_changed"):
        assert result["url"] != url, (
            f"Expected URL to change after redirect, but got same URL: {url!r}"
        )

    for key, expected in (assertions.get("fields") or {}).items():
        actual = _resolve_field(result, key)
        assert actual == expected, (
            f"Field '{key}': expected {expected!r}, got {actual!r}"
        )
