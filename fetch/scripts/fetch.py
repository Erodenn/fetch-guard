#!/usr/bin/env python3
"""Fetch skill entry point — CLI arg parsing, dependency checks, pipeline orchestration.

Usage:
    python fetch.py <url> [--timeout N] [--max-words N] [--strict]
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
import fetch_client
import html_sanitizer
import injection_guard
import output_formatter

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

    args = parser.parse_args()

    # 1. Fetch
    result = fetch_client.fetch(args.url, timeout=args.timeout)
    if result["error"]:
        print(f"Fetch error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # 2. Sanitize
    cleaned_html, tally = html_sanitizer.sanitize(result["html"])

    # 3. Extract
    markdown = content_extractor.extract(cleaned_html)
    if markdown is None:
        print("No content could be extracted from the page.", file=sys.stderr)
        sys.exit(1)

    # 4. Scan for injection
    risk_result = injection_guard.scan(markdown)

    # 5. Salt and wrap
    salt = injection_guard.generate_salt()
    salted_body = injection_guard.wrap_content(markdown, salt)

    # 6. Format output
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = output_formatter.format_output(
        url=result["final_url"],
        fetch_timestamp=timestamp,
        risk_result=risk_result,
        sanitize_tally=tally,
        salted_body=salted_body,
        max_words=args.max_words,
    )

    # 7. Print
    print(output)

    # 8. Exit code
    if args.strict and risk_result["risk"] == "HIGH":
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
