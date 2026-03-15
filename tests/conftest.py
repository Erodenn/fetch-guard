"""Shared fixtures and helpers for fetch-guard tests."""

from contextlib import ExitStack
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Builder helpers (mirrored from test_pipeline.py for cross-file use)
# ---------------------------------------------------------------------------

def _mock_fetch_result(
    html="<html><body><p>Hello world</p></body></html>",
    url="https://example.com",
    error=None,
    content_type="text/html; charset=utf-8",
):
    return {
        "status_code": 200,
        "html": html,
        "final_url": url,
        "content_type": content_type,
        "error": error,
        "headers": {},
    }


def _mock_llms_result(available=False, content=None, url=None):
    return {"available": available, "content": content, "url": url}


def _mock_edge_result(edge_type=None, detail=None, should_retry=False):
    return {
        "edge_type": edge_type,
        "detail": detail,
        "should_retry": should_retry,
    }


def _zero_tally(**overrides):
    tally = {
        "hidden_elements": 0,
        "offscreen_elements": 0,
        "nonprinting_chars": 0,
    }
    tally.update(overrides)
    return tally


def _null_meta(**overrides):
    meta = {
        "title": None, "author": None, "date": None,
        "description": None, "canonical_url": None, "image": None,
    }
    meta.update(overrides)
    return meta


_OK_SCAN = {"risk": "OK", "matches": []}


# ---------------------------------------------------------------------------
# MockedPipelineContext
# ---------------------------------------------------------------------------

@dataclass
class MockedPipelineContext:
    check_llms_txt: MagicMock
    is_root_url: MagicMock
    static_fetch: MagicMock
    playwright_fetch: MagicMock
    detect_edges: MagicMock
    extract_content: MagicMock
    sanitize: MagicMock
    extract_metadata: MagicMock
    extract_domains: MagicMock
    scan: MagicMock
    scan_metadata: MagicMock
    merge_scan_results: MagicMock

    def apply(self, overrides: dict) -> None:
        """Set return_value on named mocks. Keys are attribute names."""
        for attr, value in overrides.items():
            getattr(self, attr).return_value = value


# ---------------------------------------------------------------------------
# mocked_pipeline fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mocked_pipeline():
    with ExitStack() as stack:
        ctx = MockedPipelineContext(
            check_llms_txt=stack.enter_context(patch("fetch_guard.pipeline.check_llms_txt")),
            is_root_url=stack.enter_context(patch("fetch_guard.pipeline.is_root_url")),
            static_fetch=stack.enter_context(patch("fetch_guard.pipeline.static_fetch")),
            playwright_fetch=stack.enter_context(patch("fetch_guard.pipeline.playwright_fetch")),
            detect_edges=stack.enter_context(patch("fetch_guard.pipeline.detect_edges")),
            extract_content=stack.enter_context(patch("fetch_guard.pipeline.extract_content")),
            sanitize=stack.enter_context(patch("fetch_guard.pipeline.sanitize")),
            extract_metadata=stack.enter_context(patch("fetch_guard.pipeline.extract_metadata")),
            extract_domains=stack.enter_context(patch("fetch_guard.pipeline.extract_domains")),
            scan=stack.enter_context(patch("fetch_guard.pipeline.scan")),
            scan_metadata=stack.enter_context(patch("fetch_guard.pipeline.scan_metadata")),
            merge_scan_results=stack.enter_context(patch("fetch_guard.pipeline.merge_scan_results")),
        )
        # Sane defaults — valid happy-path pipeline state
        ctx.check_llms_txt.return_value = _mock_llms_result()
        ctx.is_root_url.return_value = False
        ctx.static_fetch.return_value = _mock_fetch_result()
        ctx.playwright_fetch.return_value = _mock_fetch_result()
        ctx.detect_edges.return_value = _mock_edge_result()
        ctx.sanitize.return_value = ("<p>Hello world</p>", None, _zero_tally())
        ctx.extract_content.return_value = "Hello world"
        ctx.extract_metadata.return_value = _null_meta()
        ctx.extract_domains.return_value = []
        ctx.scan.return_value = _OK_SCAN
        ctx.scan_metadata.return_value = _OK_SCAN
        ctx.merge_scan_results.return_value = _OK_SCAN
        yield ctx


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------

def bot_block_scenario() -> dict:
    return {"detect_edges": _mock_edge_result(edge_type="bot_block")}


def login_wall_scenario() -> dict:
    return {"detect_edges": _mock_edge_result(edge_type="login_wall")}


def paywall_scenario() -> dict:
    return {"detect_edges": _mock_edge_result(edge_type="paywall")}


def llms_txt_scenario(content: str = "# LLMs\nContent") -> dict:
    return {
        "check_llms_txt": _mock_llms_result(
            available=True, content=content, url="https://example.com/llms.txt"
        )
    }


def high_risk_scan_scenario(pattern: str = "ignore_previous") -> dict:
    match = {"pattern": pattern, "severity": "high", "snippet": "x"}
    result = {"risk": "HIGH", "matches": [match]}
    return {"scan": result, "scan_metadata": _OK_SCAN, "merge_scan_results": result}


def js_hint_scenario() -> dict:
    return {
        "static_fetch": _mock_fetch_result(html="<html><body></body></html>"),
        "extract_content": "",
    }
