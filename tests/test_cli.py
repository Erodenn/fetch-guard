"""Tests for CLI entry point."""

from unittest.mock import patch

import pytest
from fetch_guard.cli import main
from fetch_guard.pipeline import FetchError

from conftest import _build_pipeline_result

_BASE_ARGV = ["fetch-guard", "https://example.com"]

_WRAPPED_BODY = "<fetch-content-abcd1234>\nbody\n</fetch-content-abcd1234>"


def _run(*extra_args, result=None, side_effect=None):
    """Invoke main() with patched argv and dependencies.

    Returns (exit_code, mock_run) where mock_run is the patched pipeline_run.
    """
    mock_kwargs = {}
    if side_effect is not None:
        mock_kwargs["side_effect"] = side_effect
    else:
        mock_kwargs["return_value"] = result if result is not None else _build_pipeline_result()

    with (
        patch("sys.argv", [*_BASE_ARGV, *extra_args]),
        patch("fetch_guard.cli.pipeline_run", **mock_kwargs) as mock_run,
        patch("fetch_guard.cli.injection_guard.generate_salt", return_value="abcd1234"),
        patch("fetch_guard.cli.injection_guard.wrap_content", return_value=_WRAPPED_BODY),
        patch("fetch_guard.cli.output_formatter.format_output", return_value="formatted output"),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    return exc_info.value.code, mock_run


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

class TestHeaderParsing:
    """Tests for --header argument parsing."""

    def test_single_header(self):
        _, mock_run = _run("--header", "Authorization:Bearer token")
        assert mock_run.call_args.kwargs["headers"] == {"Authorization": "Bearer token"}

    def test_multiple_headers(self):
        _, mock_run = _run("--header", "Authorization:Bearer token", "--header", "X-Custom:value")
        assert mock_run.call_args.kwargs["headers"] == {
            "Authorization": "Bearer token",
            "X-Custom": "value",
        }

    def test_value_with_colon_split_on_first_only(self):
        # partition(":") splits on first ":" — rest of value preserved
        _, mock_run = _run("--header", "Content-Type:application/json; charset=utf-8")
        assert mock_run.call_args.kwargs["headers"] == {
            "Content-Type": "application/json; charset=utf-8",
        }

    def test_whitespace_stripped_from_key_and_value(self):
        # key.strip() and value.strip() are applied after partition
        _, mock_run = _run("--header", "  Authorization : Bearer token ")
        headers = mock_run.call_args.kwargs["headers"]
        assert headers == {"Authorization": "Bearer token"}

    def test_no_header_flags_passes_none(self):
        _, mock_run = _run()
        assert mock_run.call_args.kwargs["headers"] is None


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    """Tests for CLI exit codes."""

    def test_success_exits_zero(self):
        code, _ = _run()
        assert code == 0

    def test_fetch_error_exits_one(self):
        code, _ = _run(side_effect=FetchError("Connection refused"))
        assert code == 1

    def test_strict_high_risk_exits_two(self):
        result = _build_pipeline_result(
            risk_level="HIGH",
            injection_matches=[{"pattern": "ignore_previous", "severity": "high", "snippet": "ignore"}],
        )
        code, _ = _run("--strict", result=result)
        assert code == 2

    def test_strict_medium_risk_exits_zero(self):
        # strict only blocks HIGH, not MEDIUM
        result = _build_pipeline_result(
            risk_level="MEDIUM",
            injection_matches=[{"pattern": "pretend_you_are", "severity": "medium", "snippet": "pretend"}],
        )
        code, _ = _run("--strict", result=result)
        assert code == 0

    def test_not_strict_high_risk_exits_zero(self):
        result = _build_pipeline_result(risk_level="HIGH")
        code, _ = _run(result=result)
        assert code == 0


# ---------------------------------------------------------------------------
# Flag passthrough
# ---------------------------------------------------------------------------

class TestFlagPassthrough:
    """Tests that CLI flags pass correctly to pipeline_run."""

    def test_defaults(self):
        _, mock_run = _run()
        kw = mock_run.call_args.kwargs
        assert kw["timeout"] == 180
        assert kw["max_words"] is None
        assert kw["strict"] is False
        assert kw["js"] is False
        assert kw["links"] == "domains"

    def test_timeout_flag(self):
        _, mock_run = _run("--timeout", "60")
        assert mock_run.call_args.kwargs["timeout"] == 60

    def test_max_words_flag(self):
        _, mock_run = _run("--max-words", "500")
        assert mock_run.call_args.kwargs["max_words"] == 500

    def test_js_flag(self):
        _, mock_run = _run("--js")
        assert mock_run.call_args.kwargs["js"] is True

    def test_strict_flag(self):
        _, mock_run = _run("--strict")
        assert mock_run.call_args.kwargs["strict"] is True

    def test_links_full_flag(self):
        _, mock_run = _run("--links", "full")
        assert mock_run.call_args.kwargs["links"] == "full"


# ---------------------------------------------------------------------------
# URL argument
# ---------------------------------------------------------------------------

class TestURLArgument:
    """Tests for positional URL argument."""

    def test_url_passed_to_pipeline(self):
        with (
            patch("sys.argv", ["fetch-guard", "https://other.example.com"]),
            patch("fetch_guard.cli.pipeline_run", return_value=_build_pipeline_result()) as mock_run,
            patch("fetch_guard.cli.injection_guard.generate_salt", return_value="abcd1234"),
            patch("fetch_guard.cli.injection_guard.wrap_content", return_value=_WRAPPED_BODY),
            patch("fetch_guard.cli.output_formatter.format_output", return_value="ok"),
            pytest.raises(SystemExit),
        ):
            main()

        assert mock_run.call_args.kwargs["url"] == "https://other.example.com"
