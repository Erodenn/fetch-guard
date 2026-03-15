"""Core fetch pipeline — URL to structured result dict.

Extracts the pipeline logic from the CLI entry point so it can be reused
by both the CLI (fetch.py) and the MCP server (server.py).
"""

import concurrent.futures
from datetime import datetime, timezone

from .extraction import (
    CLASS_BINARY,
    CLASS_HTML,
    CLASS_UNKNOWN,
    classify_content_type,
    detect_edges,
    extract_content,
    extract_domains,
    extract_full,
    extract_metadata,
    handle_content_type,
    null_metadata,
)
from .http import (
    BROWSER_USER_AGENT,
    check_llms_txt,
    is_root_url,
    playwright_fetch,
    static_fetch,
)
from .security import merge_scan_results, sanitize, scan, scan_metadata

_ZERO_TALLY = {"hidden_elements": 0, "offscreen_elements": 0, "nonprinting_chars": 0}

_MAX_RAW_BYTES = 2 * 1024 * 1024   # 2MB  — pre-extraction sanity guard
_MAX_EXTRACTED_BYTES = 20 * 1024    # 20KB — post-extraction LLM context guard


class FetchError(Exception):
    """Raised when the fetch pipeline encounters a non-recoverable error."""


def _truncate(text, max_words):
    """Truncate text to a word limit. Returns (text, truncated_at)."""
    if max_words is None:
        return text, None
    parts = text.split(maxsplit=max_words)
    if len(parts) > max_words:
        return " ".join(parts[:max_words]), max_words
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
    # `strict` is accepted for API symmetry but not used here — callers
    # (server.py, cli.py) inspect `risk_level` in the result dict to decide
    # whether to raise/exit on high-risk injection.
    js_rendered = js
    edge_result = None
    retried = False
    js_hint = False

    # 1. Check for /llms.txt + fetch
    fetcher = playwright_fetch if js else static_fetch
    is_root = is_root_url(url)
    llms_txt_replaced = False

    if is_root:
        # Sequential: check llms.txt first — may replace the entire fetch
        llms_result = check_llms_txt(url)
        llms_txt_available = llms_result["available"]

        if llms_txt_available:
            llms_txt_replaced = True
            raw_html = llms_result["content"]
            final_url = llms_result["url"]
            content_type = ""
        else:
            result = fetcher(url, timeout=timeout)
            if result["error"]:
                raise FetchError(result["error"])
            edge_result = detect_edges(result)
            raw_html = result["html"]
            final_url = result["final_url"]
            content_type = result.get("content_type", "")
    else:
        # Concurrent: fetch + llms.txt check in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            llms_future = executor.submit(check_llms_txt, url)
            fetch_future = executor.submit(fetcher, url, timeout=timeout)
            result = fetch_future.result()
            llms_result = llms_future.result()

        llms_txt_available = llms_result["available"]

        if result["error"]:
            raise FetchError(result["error"])

        # 3. Edge detection
        edge_result = detect_edges(result)

        raw_html = result["html"]
        final_url = result["final_url"]
        content_type = result.get("content_type", "")

    # 4. Retry with browser UA if bot block detected (static only, non-root)
    if not llms_txt_replaced and edge_result and edge_result["should_retry"] and not js:
        retried = True
        result = static_fetch(
            url,
            timeout=timeout,
            user_agent=BROWSER_USER_AGENT,
        )
        if result["error"]:
            raise FetchError(f"Error on retry: {result['error']}")
        edge_result = detect_edges(result)
        raw_html = result["html"]
        final_url = result["final_url"]
        content_type = result.get("content_type", "")

    # Size guard — pre-extraction
    if max_words is None:
        raw_size = len(raw_html.encode("utf-8"))
        if raw_size > _MAX_RAW_BYTES:
            raise FetchError(
                f"Raw content too large: {raw_size // 1024}KB (limit: {_MAX_RAW_BYTES // 1024}KB). "
                f"Pass max_words to disable the size guard and fetch with explicit truncation."
            )

    # 5. Content-type routing — non-HTML gets its own fast path
    if not llms_txt_replaced:
        content_class = classify_content_type(
            content_type, (raw_html[:500] if raw_html else ""),
        )
    else:
        content_class = CLASS_HTML  # llms.txt always uses the HTML path

    if content_class == CLASS_BINARY:
        raise FetchError(
            f"Binary content type not supported: {content_type}"
        )

    if content_class not in (CLASS_HTML, CLASS_UNKNOWN):

        markdown = handle_content_type(content_class, raw_html)
        risk_result = scan(markdown)
        if max_words is None:
            extracted_size = len(markdown.encode("utf-8"))
            if extracted_size > _MAX_EXTRACTED_BYTES:
                word_count = len(markdown.split())
                raise FetchError(
                    f"Extracted content too large: {extracted_size // 1024}KB (~{word_count:,} words, "
                    f"limit: {_MAX_EXTRACTED_BYTES // 1024}KB). "
                    f"Pass max_words={word_count} to disable the size guard, or a lower value to truncate."
                )
        markdown, truncated_at = _truncate(markdown, max_words)

        return _build_result(
            url=final_url,
            body=markdown,
            content_type=content_class,
            metadata=null_metadata(),
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
    cleaned_html, soup, tally = sanitize(raw_html)

    # 8. Extract content
    markdown = extract_content(cleaned_html)
    if markdown is None:
        if not js:
            js_hint = True
            markdown = "[No content could be extracted from this page using static fetching.]"
        else:
            msg = "No content could be extracted from the page."
            if edge_result and edge_result["edge_type"]:
                msg += f" Detected edge case: {edge_result['edge_type']} ({edge_result['detail']})"
            raise FetchError(msg)

    # 9. Extract metadata (reuse sanitized soup to avoid re-parsing)
    metadata = null_metadata() if llms_txt_replaced else extract_metadata(cleaned_html, soup=soup)

    # 10. Extract links (reuse sanitized soup to avoid re-parsing)
    if llms_txt_replaced:
        extracted_links = [] if links == "domains" else {}
    elif links == "full":
        extracted_links = extract_full(cleaned_html, url, soup=soup)
    else:
        extracted_links = extract_domains(cleaned_html, url, soup=soup)

    # 11. Scan for injection
    body_risk = scan(markdown)
    meta_risk = scan_metadata(metadata)
    risk_result = merge_scan_results([body_risk, meta_risk])

    # Size guard — post-extraction (HTML path)
    if max_words is None:
        extracted_size = len(markdown.encode("utf-8"))
        if extracted_size > _MAX_EXTRACTED_BYTES:
            word_count = len(markdown.split())
            raise FetchError(
                f"Extracted content too large: {extracted_size // 1024}KB (~{word_count:,} words, "
                f"limit: {_MAX_EXTRACTED_BYTES // 1024}KB). "
                f"Pass max_words={word_count} to disable the size guard, or a lower value to truncate."
            )

    # 12. Truncate
    markdown, truncated_at = _truncate(markdown, max_words)

    # 13. Build result
    return _build_result(
        url=final_url,
        body=markdown,
        content_type=CLASS_HTML,
        metadata=metadata,
        links=extracted_links,
        links_mode=links,
        risk_result=risk_result,
        edge_result=edge_result,
        sanitization=tally,
        llms_txt_available=llms_txt_available,
        llms_txt_replaced=llms_txt_replaced,
        js_rendered=js_rendered,
        js_hint=js_hint,
        retried=retried,
        truncated_at=truncated_at,
    )
