"""Core fetch pipeline — URL to structured result dict.

Extracts the pipeline logic from the CLI entry point so it can be reused
by both the CLI (fetch.py) and the MCP server (server.py).
"""

import os
from datetime import datetime, timezone

# Ensure consistent UTF-8 output on Windows
if not os.environ.get("PYTHONIOENCODING"):
    os.environ["PYTHONIOENCODING"] = "utf-8"

from . import (
    content_extractor,
    content_type_handler,
    edge_detector,
    fetch_client,
    html_sanitizer,
    injection_guard,
    link_extractor,
    llms_txt_checker,
    metadata_extractor,
    playwright_fetcher,
)

_ZERO_TALLY = {"hidden_elements": 0, "offscreen_elements": 0, "nonprinting_chars": 0}


class FetchError(Exception):
    """Raised when the fetch pipeline encounters a non-recoverable error."""


def _truncate(text, max_words):
    """Truncate text to a word limit. Returns (text, truncated_at)."""
    if max_words is None:
        return text, None
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]), max_words
    return text, None


def _build_edge_cases(edge_result):
    """Build the edge_cases dict from an edge detector result, or None."""
    if edge_result and edge_result["edge_type"]:
        return {
            "type": edge_result["edge_type"],
            "detail": edge_result["detail"],
        }
    return None


def _build_result(
    *,
    url,
    body,
    content_type,
    metadata,
    links,
    links_mode,
    risk_result,
    edge_result,
    sanitization,
    llms_txt_available,
    llms_txt_replaced,
    js_rendered,
    js_hint,
    retried,
    truncated_at,
):
    """Assemble the final pipeline result dict."""
    return {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "body": body,
        "content_type": content_type,
        "metadata": metadata,
        "links": links,
        "links_mode": links_mode,
        "risk_level": risk_result["risk"],
        "injection_matches": risk_result["matches"],
        "edge_cases": _build_edge_cases(edge_result),
        "sanitization": sanitization,
        "llms_txt_available": llms_txt_available,
        "llms_txt_replaced": llms_txt_replaced,
        "js_rendered": js_rendered,
        "js_hint": js_hint,
        "retried": retried,
        "truncated_at": truncated_at,
    }


def run(url, timeout=180, max_words=None, strict=False, js=False, links="domains"):
    """Execute the fetch pipeline.

    Args:
        url: URL to fetch.
        timeout: Request timeout in seconds.
        max_words: Optional word cap on extracted body content.
        strict: If True, does not change the return value — callers check
                risk_level themselves to decide on error behavior.
        js: Use Playwright for JavaScript rendering.
        links: "domains" or "full" link extraction mode.

    Returns:
        A structured dict with all pipeline results.

    Raises:
        FetchError: On network/fetch failures or empty responses.
    """
    js_rendered = js
    edge_result = None
    retried = False
    js_hint = False

    # 1. Check for /llms.txt
    llms_result = llms_txt_checker.check(url)
    llms_txt_available = llms_result["available"]
    llms_txt_replaced = False

    if llms_txt_available and llms_txt_checker.is_root_url(url):
        llms_txt_replaced = True
        raw_html = llms_result["content"]
        final_url = llms_result["url"]
        content_type = ""
    else:
        # 2. Fetch — Playwright or static
        fetcher = playwright_fetcher if js else fetch_client
        result = fetcher.fetch(url, timeout=timeout)

        if result["error"]:
            raise FetchError(result["error"])

        # 3. Edge detection
        edge_result = edge_detector.detect(result)

        # 4. Retry with browser UA if bot block detected (static only)
        if edge_result["should_retry"] and not js:
            retried = True
            result = fetch_client.fetch(
                url,
                timeout=timeout,
                user_agent=fetch_client.BROWSER_USER_AGENT,
            )
            if result["error"]:
                raise FetchError(f"Error on retry: {result['error']}")
            edge_result = edge_detector.detect(result)

        raw_html = result["html"]
        final_url = result["final_url"]
        content_type = result.get("content_type", "")

    # 5. Content-type routing — non-HTML gets its own fast path
    if not llms_txt_replaced:
        content_class = content_type_handler.classify(
            content_type, (raw_html[:500] if raw_html else ""),
        )
    else:
        content_class = "html"  # llms.txt always uses the HTML path

    if content_class == "binary":
        raise FetchError(
            f"Binary content type not supported: {content_type}"
        )

    if content_class not in ("html", "unknown"):

        markdown = content_type_handler.handle(content_class, raw_html)
        risk_result = injection_guard.scan(markdown)
        markdown, truncated_at = _truncate(markdown, max_words)

        return _build_result(
            url=final_url,
            body=markdown,
            content_type=content_class,
            metadata=metadata_extractor.null_metadata(),
            links=[] if links == "domains" else {},
            links_mode=links,
            risk_result=risk_result,
            edge_result=edge_result,
            sanitization=_ZERO_TALLY,
            llms_txt_available=llms_txt_available,
            llms_txt_replaced=False,
            js_rendered=js_rendered,
            js_hint=False,
            retried=retried,
            truncated_at=truncated_at,
        )

    # --- HTML path ---

    # 6. Check we have HTML to work with
    if not raw_html:
        raise FetchError("No response body received.")

    # 7. Sanitize
    cleaned_html, tally = html_sanitizer.sanitize(raw_html)

    # 8. Extract content
    markdown = content_extractor.extract(cleaned_html)
    if markdown is None:
        if not js:
            js_hint = True
            markdown = "[No content could be extracted from this page using static fetching.]"
        else:
            msg = "No content could be extracted from the page."
            if edge_result and edge_result["edge_type"]:
                msg += f" Detected edge case: {edge_result['edge_type']} ({edge_result['detail']})"
            raise FetchError(msg)

    # 9. Extract metadata
    metadata = metadata_extractor.null_metadata() if llms_txt_replaced else metadata_extractor.extract(cleaned_html)

    # 10. Extract links
    if llms_txt_replaced:
        extracted_links = [] if links == "domains" else {}
    elif links == "full":
        extracted_links = link_extractor.extract_full(cleaned_html, url)
    else:
        extracted_links = link_extractor.extract_domains(cleaned_html, url)

    # 11. Scan for injection
    risk_result = injection_guard.scan(markdown)

    # 12. Truncate
    markdown, truncated_at = _truncate(markdown, max_words)

    # 13. Build result
    return _build_result(
        url=final_url,
        body=markdown,
        content_type="html",
        metadata=metadata,
        links=extracted_links,
        links_mode=links,
        risk_result=risk_result,
        edge_result=edge_result,
        sanitization={
            "hidden_elements": tally.get("hidden_elements", 0),
            "offscreen_elements": tally.get("offscreen_elements", 0),
            "nonprinting_chars": tally.get("nonprinting_chars", 0),
        },
        llms_txt_available=llms_txt_available,
        llms_txt_replaced=llms_txt_replaced,
        js_rendered=js_rendered,
        js_hint=js_hint,
        retried=retried,
        truncated_at=truncated_at,
    )
