"""Session-salted tag wrapping, injection pattern scanning, and risk assessment."""

import base64
import codecs
import re
import secrets
import urllib.parse
from collections.abc import Callable
from typing import Any

from .normalize import normalize_for_scan
from .patterns import HIGH_PATTERNS, PATTERNS, SEVERITY_HIGH

CONTEXT_CHARS = 60

# Risk levels — use these constants instead of raw strings
RISK_OK = "OK"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

# Decode-and-scan candidate regexes
_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_HEX_RE = re.compile(r"(?:[0-9a-fA-F]{2}){20,}")
# 3+ consecutive %XX sequences — avoids false positives from incidental single-char encoding
_PERCENT_RE = re.compile(r"(?:%[0-9a-fA-F]{2}){3,}")


def generate_salt() -> str:
    """Return an 8-char random hex string."""
    return secrets.token_hex(4)


def wrap_content(text: str, salt: str) -> str:
    """Wrap text in session-salted fetch-content tags."""
    return f"<fetch-content-{salt}>\n{text}\n</fetch-content-{salt}>"


def _snippet(text: str, match: re.Match[str]) -> str:
    """Extract a context snippet around a regex match."""
    start = max(0, match.start() - CONTEXT_CHARS)
    end = min(len(text), match.end() + CONTEXT_CHARS)
    return text[start:end].replace("\n", " ").strip()


def _rot13(text: str) -> str:
    """Decode ROT13-encoded text. ASCII letters rotate; non-ASCII pass through unchanged."""
    return codecs.encode(text, "rot_13")


def _decode_base64(candidate: str) -> str:
    """Try to decode a base64 candidate to UTF-8 text."""
    try:
        return base64.b64decode(candidate).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _decode_hex(candidate: str) -> str:
    """Try to decode a hex candidate to UTF-8 text."""
    try:
        return bytes.fromhex(candidate).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _decode_url(candidate: str) -> str:
    """Decode a URL percent-encoded candidate to UTF-8 text."""
    try:
        return urllib.parse.unquote(candidate, errors="ignore")
    except Exception:
        return ""


def _scan_decoded(
    text: str,
    candidates_regex: re.Pattern[str],
    decoder_fn: Callable[[str], str],
    prefix: str,
) -> list[dict[str, str]]:
    """Find encoded candidates in text, decode each, scan with HIGH patterns.

    Returns list of match dicts with prefixed pattern names.
    """
    matches: list[dict[str, str]] = []
    for candidate_match in candidates_regex.finditer(text):
        candidate = candidate_match.group()
        decoded = decoder_fn(candidate)
        if not decoded or len(decoded) < 8:
            continue
        for name, pattern, severity in HIGH_PATTERNS:
            for _hit in pattern.finditer(decoded):
                matches.append(
                    {
                        "pattern": f"{prefix}:{name}",
                        "severity": severity,
                        "snippet": _snippet(text, candidate_match),
                    }
                )
                break  # one match per pattern per candidate is enough
    return matches


def scan(text: str) -> dict[str, Any]:
    """Scan text for injection patterns.

    Four-phase scan:
    1. Run all PATTERNS against original text
    2. Normalize text (NFKC + confusable mapping), scan again for homoglyph bypasses
    3. Decode-and-scan: find base64/hex/URL-percent-encoded blocks, decode, scan with HIGH patterns
    4. ROT13 whole-document scan with HIGH patterns

    Returns a dict with:
        risk: "OK", "MEDIUM", or "HIGH"
        matches: list of {pattern, severity, snippet}
    """
    matches: list[dict[str, str]] = []

    # Phase 1: Scan original text with all patterns
    original_hits: dict[str, set[tuple[int, int]]] = {}  # name → list of match positions
    for name, pattern, severity in PATTERNS:
        for match in pattern.finditer(text):
            matches.append(
                {
                    "pattern": name,
                    "severity": severity,
                    "snippet": _snippet(text, match),
                }
            )
            original_hits.setdefault(name, set()).add((match.start(), match.end()))

    # Phase 2: Homoglyph normalization scan
    normalized = normalize_for_scan(text)
    if normalized != text:
        for name, pattern, severity in PATTERNS:
            for match in pattern.finditer(normalized):
                # Skip if this pattern already matched at roughly the same position
                if name in original_hits:
                    # Check if any original hit overlaps with this normalized hit
                    already_found = any(
                        abs(match.start() - orig_start) < 10 for orig_start, _orig_end in original_hits[name]
                    )
                    if already_found:
                        continue
                matches.append(
                    {
                        "pattern": f"homoglyph:{name}",
                        "severity": severity,
                        "snippet": _snippet(normalized, match),
                    }
                )

    # Phase 3: Decode-and-scan (base64, hex, and URL percent-encoding)
    matches.extend(_scan_decoded(text, _BASE64_RE, _decode_base64, "base64_decoded"))
    matches.extend(_scan_decoded(text, _HEX_RE, _decode_hex, "hex_decoded"))
    matches.extend(_scan_decoded(text, _PERCENT_RE, _decode_url, "urldecoded"))

    # Phase 4: ROT13 whole-document scan (HIGH patterns only)
    rot13_text = _rot13(text)
    if rot13_text != text:
        for name, pattern, severity in HIGH_PATTERNS:
            for match in pattern.finditer(rot13_text):
                matches.append(
                    {
                        "pattern": f"rot13:{name}",
                        "severity": severity,
                        "snippet": _snippet(rot13_text, match),
                    }
                )

    return _risk_from_matches(matches)


def _risk_from_matches(matches: list[dict[str, str]]) -> dict[str, Any]:
    """Determine risk level from a list of match dicts."""
    if not matches:
        return {"risk": RISK_OK, "matches": []}
    risk = RISK_HIGH if any(m["severity"] == SEVERITY_HIGH for m in matches) else RISK_MEDIUM
    return {"risk": risk, "matches": matches}


def scan_metadata(metadata_dict: dict[str, Any]) -> dict[str, Any]:
    """Scan metadata string fields for injection patterns.

    Each match's pattern name is prefixed with "metadata:{field}:" to
    indicate which field the injection was found in.
    Returns {risk, matches} with the same structure as scan().
    """
    all_matches: list[dict[str, str]] = []
    for field, value in metadata_dict.items():
        if not isinstance(value, str) or not value:
            continue
        result = scan(value)
        for match in result["matches"]:
            all_matches.append(
                {
                    "pattern": f"metadata:{field}:{match['pattern']}",
                    "severity": match["severity"],
                    "snippet": match["snippet"],
                }
            )
    return _risk_from_matches(all_matches)


def merge_scan_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a list of scan result dicts. Risk level is the highest across all."""
    all_matches = [m for r in results for m in r["matches"]]
    return _risk_from_matches(all_matches)
