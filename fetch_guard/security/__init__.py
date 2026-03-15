"""Injection defense — pattern scanning, risk assessment, HTML sanitization, and salt wrapping."""

from .guard import (
    RISK_HIGH,
    RISK_MEDIUM,
    RISK_OK,
    generate_salt,
    merge_scan_results,
    scan,
    scan_metadata,
    wrap_content,
)
from .sanitizer import sanitize

__all__ = [
    "RISK_HIGH",
    "RISK_MEDIUM",
    "RISK_OK",
    "generate_salt",
    "merge_scan_results",
    "sanitize",
    "scan",
    "scan_metadata",
    "wrap_content",
]
