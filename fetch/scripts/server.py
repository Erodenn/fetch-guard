"""MCP server wrapper for the fetch pipeline.

Exposes the fetch pipeline as an MCP tool via FastMCP (stdio transport).

Usage:
    python server.py              # direct
    fetch-mcp                     # via console_scripts entry point
"""

import os
import sys

# Ensure consistent UTF-8 output on Windows
if not os.environ.get("PYTHONIOENCODING"):
    os.environ["PYTHONIOENCODING"] = "utf-8"

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

REQUIRED_DEPS = {
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "trafilatura": "trafilatura",
    "extruct": "extruct",
    "mcp": "mcp",
}

_missing = []
for _module, _package in REQUIRED_DEPS.items():
    try:
        __import__(_module)
    except ImportError:
        _missing.append(_package)

if _missing:
    print(
        f"Missing dependencies: {', '.join(_missing)}\n"
        f"Install with: pip install {' '.join(_missing)}",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Imports (after dependency check)
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from mcp.server.fastmcp import FastMCP

import injection_guard
from pipeline import FetchError
from pipeline import run as pipeline_run

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("fetch", json_response=True)


@mcp.tool()
def fetch(
    url: str,
    timeout: int = 180,
    max_words: int | None = None,
    strict: bool = False,
    js: bool = False,
    links: str = "domains",
) -> dict:
    """Fetch a URL and return clean, LLM-ready markdown with metadata and prompt injection scanning.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        max_words: Optional word cap on extracted body content.
        strict: When True and high-risk injection is detected, the response is marked as an error.
        js: Use Playwright for JavaScript-rendered pages (requires playwright + chromium).
        links: Link extraction mode — "domains" (default) or "full" for all URLs with anchor text.

    Returns:
        A structured dict with url, body (markdown), metadata, links, risk_level,
        injection_matches, sanitization stats, and edge case info.
    """
    try:
        result = pipeline_run(
            url=url,
            timeout=timeout,
            max_words=max_words,
            strict=strict,
            js=js,
            links=links,
        )
    except FetchError as e:
        raise ValueError(str(e)) from e

    # Salt-wrap the body for defense-in-depth — even in structured JSON,
    # the body may be interpolated into a prompt by the consuming client.
    salt = injection_guard.generate_salt()
    result["body"] = injection_guard.wrap_content(result["body"], salt)

    # For strict mode + HIGH risk, raise so FastMCP marks the response as an error.
    # The caller still gets the full result in the error message.
    if strict and result["risk_level"] == injection_guard.RISK_HIGH:
        raise ValueError(
            f"High-risk prompt injection detected ({len(result['injection_matches'])} matches). "
            f"URL: {result['url']}"
        )

    return result


def main():
    """Run the MCP server on stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
