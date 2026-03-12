#!/usr/bin/env python3
"""Fetch skill entry point — CLI arg parsing, dependency checks, pipeline orchestration.

Usage:
    python fetch.py <url> [--timeout N] [--max-words N] [--strict] [--links domains|full]
"""

import argparse
import os
import sys

# Ensure consistent UTF-8 output on Windows
if not os.environ.get("PYTHONIOENCODING"):
    os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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

import injection_guard
import output_formatter
from pipeline import FetchError
from pipeline import run as pipeline_run

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

    # 1. Run the pipeline
    try:
        result = pipeline_run(
            url=args.url,
            timeout=args.timeout,
            max_words=args.max_words,
            strict=args.strict,
            js=args.js,
            links=args.links,
        )
    except FetchError as e:
        print(f"Fetch error: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Salt and wrap body for CLI text output
    salt = injection_guard.generate_salt()
    salted_body = injection_guard.wrap_content(result["body"], salt)

    # 3. Reconstruct risk_result dict for output_formatter
    risk_result = {
        "risk": result["risk_level"],
        "matches": result["injection_matches"],
    }

    # 4. Reconstruct edge fields
    edge_type = result["edge_cases"]["type"] if result["edge_cases"] else None
    edge_detail = result["edge_cases"]["detail"] if result["edge_cases"] else None

    # 5. Format output
    output = output_formatter.format_output(
        url=result["url"],
        fetch_timestamp=result["fetched_at"],
        risk_result=risk_result,
        sanitize_tally=result["sanitization"],
        salted_body=salted_body,
        truncated_at=result["truncated_at"],
        metadata=result["metadata"],
        links=result["links"],
        links_mode=result["links_mode"],
        llms_txt_available=result["llms_txt_available"],
        llms_txt_replaced=result["llms_txt_replaced"],
        js_rendered=result["js_rendered"],
        edge_type=edge_type,
        edge_detail=edge_detail,
        retried=result["retried"],
        js_hint=result["js_hint"],
    )

    # 6. Print
    print(output)

    # 7. Exit code
    if args.strict and result["risk_level"] == injection_guard.RISK_HIGH:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
