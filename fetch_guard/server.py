"""MCP server wrapper for the fetch pipeline.

Exposes the fetch pipeline as an MCP tool via FastMCP (stdio transport).

Usage:
    python server.py              # direct
    fetch-guard                    # via console_scripts entry point
"""

from . import check_deps

check_deps(extra={"mcp": "mcp"})

# ---------------------------------------------------------------------------
# Imports (after dependency check)
# ---------------------------------------------------------------------------

import warnings
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .pipeline import FetchError
from .pipeline import run as pipeline_run
from .security import guard as injection_guard

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("fetch-guard", json_response=True)


@mcp.tool()
def fetch(
    url: str,
    timeout: int = 180,
    max_words: int | None = None,
    strict: bool = False,
    js: bool = False,
    links: Literal["domains", "full"] = "domains",
    auth_token: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    """Fetch a URL and return clean, LLM-ready markdown with metadata and prompt injection scanning.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        max_words: Optional word cap on extracted body content.
        strict: When True and high-risk injection is detected, the response is marked as an error.
        js: Use Playwright for JavaScript-rendered pages (requires playwright + chromium).
        links: Link extraction mode — "domains" (default) or "full" for all URLs with anchor text.
        auth_token: Bearer token for Authorization header (e.g. "my-api-key").
        headers: Deprecated. Use auth_token instead. Custom HTTP headers to include in the request.

    Returns:
        A structured dict with url, body (markdown), metadata, links, risk_level,
        injection_matches, sanitization stats, and edge case info.
    """
    if headers is not None:
        warnings.warn(
            "The 'headers' parameter is deprecated and will be removed in the next release. "
            "Use 'auth_token' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    resolved_headers: dict[str, str] | None = headers
    if auth_token is not None:
        resolved_headers = {**(resolved_headers or {}), "Authorization": f"Bearer {auth_token}"}

    try:
        result = pipeline_run(
            url=url,
            timeout=timeout,
            max_words=max_words,
            strict=strict,
            js=js,
            links=links,
            headers=resolved_headers,
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
