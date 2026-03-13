"""Fetch Guard — LLM-ready web fetching with prompt injection defense."""

import os
import sys

# Ensure consistent UTF-8 output on Windows
if not os.environ.get("PYTHONIOENCODING"):
    os.environ["PYTHONIOENCODING"] = "utf-8"


def check_deps(extra=None):
    """Check that required packages are importable, exit with helpful message if not.

    Args:
        extra: Optional dict of additional {module: package} pairs to check
               (e.g. {"mcp": "mcp"} for the server entry point).
    """
    required = {
        "requests": "requests",
        "bs4": "beautifulsoup4",
        "trafilatura": "trafilatura",
        "extruct": "extruct",
    }
    if extra:
        required.update(extra)

    missing = []
    for module, package in required.items():
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
