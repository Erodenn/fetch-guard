#!/usr/bin/env python3
"""Fetch Guard CLI entry point — CLI arg parsing, dependency checks, pipeline orchestration.

Usage:
    python fetch.py <url> [--timeout N] [--max-words N] [--strict] [--links domains|full]
"""

import argparse
import sys

from . import check_deps

check_deps()

# Ensure consistent UTF-8 CLI output on Windows
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Local imports (after dependency check so errors are clear)
# ---------------------------------------------------------------------------

from .output import formatter as output_formatter
from .pipeline import FetchError
from .pipeline import run as pipeline_run
from .security import guard as injection_guard

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
    parser.add_argument(
        "--header", action="append", dest="headers", metavar="KEY:VALUE",
        help="Custom HTTP header (repeatable, e.g. --header Authorization:Bearer token)",
    )

    args = parser.parse_args()

    headers = None
    if args.headers:
        headers = {}
        for h in args.headers:
            key, _, value = h.partition(":")
            headers[key.strip()] = value.strip()

    # 1. Run the pipeline
    try:
        result = pipeline_run(
            url=args.url,
            timeout=args.timeout,
            max_words=args.max_words,
            strict=args.strict,
            js=args.js,
            links=args.links,
            headers=headers,
        )
    except FetchError as e:
        print(f"Fetch error: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Salt and wrap body for CLI text output
    salt = injection_guard.generate_salt()
    salted_body = injection_guard.wrap_content(result["body"], salt)

    # 3. Format and print
    print(output_formatter.format_output(result, salted_body))

    # 4. Exit code
    if args.strict and result["risk_level"] == injection_guard.RISK_HIGH:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
