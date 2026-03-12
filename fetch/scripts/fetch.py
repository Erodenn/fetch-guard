#!/usr/bin/env python3
"""Fetch skill entry point — CLI arg parsing, dependency checks, pipeline orchestration.

Usage:
    python fetch.py <url> [--timeout N] [--max-words N] [--strict] [--links domains|full]
"""

import argparse
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

REQUIRED_DEPS = {
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "trafilatura": "trafilatura",
    "extruct": "extruct",
}

missing = []
for module, package in REQUIRED_DEPS.items():
    try:
        __import__(module)
    except ImportError:
        missing.append(package)

if missing:
    print(
        f"Missing dependencies: {', '.join(missing)}\n"
        f"Install with: pip install {' '.join(missing)}",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Local imports (after dependency check so errors are clear)
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import content_extractor
import edge_detector
import fetch_client
import html_sanitizer
import injection_guard
import link_extractor
import llms_txt_checker
import metadata_extractor
import output_formatter
import playwright_fetcher

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch a URL and return clean, LLM-ready markdown with injection safety scanning.",
    )
    parser.add_argument(
        "url",
        help="URL to fetch",
    )
    parser.add_argument(
        "--timeout", type=int, default=180,
        help="Request timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--max-words", type=int, default=None,
        help="Optional word cap on extracted body content",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit nonzero (code 2) on high-risk injection detection",
    )
    parser.add_argument(
        "--links", choices=["domains", "full"], default="domains",
        help="Link extraction mode: 'domains' (default) or 'full' for all URLs with anchor text",
    )
    parser.add_argument(
        "--js", action="store_true",
        help="Use Playwright for JavaScript-rendered pages (requires playwright + chromium)",
    )

    args = parser.parse_args()

    js_rendered = args.js
    edge_result = None
    retried = False
    js_hint = False

    # 1. Check for /llms.txt
    llms_result = llms_txt_checker.check(args.url)
    llms_txt_available = llms_result["available"]
    llms_txt_replaced = False

    if llms_txt_available and llms_txt_checker.is_root_url(args.url):
        # Use /llms.txt content instead of fetching the page
        llms_txt_replaced = True
        raw_html = llms_result["content"]
        final_url = llms_result["url"]
    else:
        # 2. Fetch — Playwright or static
        if args.js:
            result = playwright_fetcher.fetch(args.url, timeout=args.timeout)
        else:
            result = fetch_client.fetch(args.url, timeout=args.timeout)

        if result["error"]:
            print(f"Fetch error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        # 3. Edge detection
        edge_result = edge_detector.detect(result)

        # 4. Retry with browser UA if bot block detected (static only)
        if edge_result["should_retry"] and not args.js:
            retried = True
            result = fetch_client.fetch(
                args.url,
                timeout=args.timeout,
                user_agent=fetch_client.BROWSER_USER_AGENT,
            )
            if result["error"]:
                print(f"Fetch error on retry: {result['error']}", file=sys.stderr)
                sys.exit(1)
            edge_result = edge_detector.detect(result)

        # 5. Check we have HTML to work with
        if not result["html"]:
            print("No response body received.", file=sys.stderr)
            sys.exit(1)

        raw_html = result["html"]
        final_url = result["final_url"]

    # 6. Sanitize (runs on llms.txt content too)
    cleaned_html, tally = html_sanitizer.sanitize(raw_html)

    # 7. Extract content
    markdown = content_extractor.extract(cleaned_html)
    if markdown is None:
        if not args.js:
            # Suggest JS rendering instead of hard failure
            js_hint = True
            markdown = "[No content could be extracted from this page using static fetching.]"
        else:
            msg = "No content could be extracted from the page."
            if edge_result and edge_result["edge_type"]:
                msg += f" Detected edge case: {edge_result['edge_type']} ({edge_result['detail']})"
            print(msg, file=sys.stderr)
            sys.exit(1)

    # 8. Extract metadata (skip if llms.txt replaced — no HTML structure)
    metadata = metadata_extractor._null_metadata() if llms_txt_replaced else metadata_extractor.extract(cleaned_html)

    # 9. Extract links (skip if llms.txt replaced — no HTML links)
    if llms_txt_replaced:
        links = [] if args.links == "domains" else {}
    elif args.links == "full":
        links = link_extractor.extract_full(cleaned_html, args.url)
    else:
        links = link_extractor.extract_domains(cleaned_html, args.url)

    # 10. Scan for injection
    risk_result = injection_guard.scan(markdown)

    # 11. Truncate before wrapping so salted tags stay intact
    truncated = False
    if args.max_words is not None:
        words = markdown.split()
        if len(words) > args.max_words:
            markdown = " ".join(words[:args.max_words])
            truncated = True

    # 12. Salt and wrap
    salt = injection_guard.generate_salt()
    salted_body = injection_guard.wrap_content(markdown, salt)

    # 13. Format output
    edge_type = edge_result["edge_type"] if edge_result else None
    edge_detail = edge_result["detail"] if edge_result else None
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = output_formatter.format_output(
        url=final_url,
        fetch_timestamp=timestamp,
        risk_result=risk_result,
        sanitize_tally=tally,
        salted_body=salted_body,
        truncated_at=args.max_words if truncated else None,
        metadata=metadata,
        links=links,
        links_mode=args.links,
        llms_txt_available=llms_txt_available,
        llms_txt_replaced=llms_txt_replaced,
        js_rendered=js_rendered,
        edge_type=edge_type,
        edge_detail=edge_detail,
        retried=retried,
        js_hint=js_hint,
    )

    # 14. Print
    print(output)

    # 15. Exit code
    if args.strict and risk_result["risk"] == "HIGH":
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
