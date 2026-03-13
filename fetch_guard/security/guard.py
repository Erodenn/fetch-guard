"""Session-salted tag wrapping, injection pattern scanning, and risk assessment."""

import base64
import re
import secrets

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


def generate_salt():
    """Return an 8-char random hex string."""
    return secrets.token_hex(4)


def wrap_content(text, salt):
    """Wrap text in session-salted fetch-content tags."""
    return f"<fetch-content-{salt}>\n{text}\n</fetch-content-{salt}>"


def _snippet(text, match):
    """Extract a context snippet around a regex match."""
    start = max(0, match.start() - CONTEXT_CHARS)
    end = min(len(text), match.end() + CONTEXT_CHARS)
    return text[start:end].replace("\n", " ").strip()


def _decode_base64(candidate):
    """Try to decode a base64 candidate to UTF-8 text."""
    try:
        return base64.b64decode(candidate).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _decode_hex(candidate):
    """Try to decode a hex candidate to UTF-8 text."""
    try:
        return bytes.fromhex(candidate).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _scan_decoded(text, candidates_regex, decoder_fn, prefix):
    """Find encoded candidates in text, decode each, scan with HIGH patterns.

    Returns list of match dicts with prefixed pattern names.
    """
    matches = []
    for candidate_match in candidates_regex.finditer(text):
        candidate = candidate_match.group()
        decoded = decoder_fn(candidate)
        if not decoded or len(decoded) < 8:
            continue
        for name, pattern, severity in HIGH_PATTERNS:
            for _hit in pattern.finditer(decoded):
                matches.append({
                    "pattern": f"{prefix}:{name}",
                    "severity": severity,
                    "snippet": text[
                        max(0, candidate_match.start() - 20):
                        min(len(text), candidate_match.end() + 20)
                    ].replace("\n", " ").strip(),
                })
                break  # one match per pattern per candidate is enough
    return matches


def scan(text):
    """Scan text for injection patterns.

    Three-phase scan:
    1. Run all PATTERNS against original text
    2. Normalize text (NFKC + confusable mapping), scan again for homoglyph bypasses
    3. Decode-and-scan: find base64/hex encoded blocks, decode, scan with HIGH patterns

    Returns a dict with:
        risk: "OK", "MEDIUM", or "HIGH"
        matches: list of {pattern, severity, snippet}
    """
    matches = []

    # Phase 1: Scan original text with all patterns
    original_hits = {}  # name → list of match positions
    for name, pattern, severity in PATTERNS:
        for match in pattern.finditer(text):
            matches.append({
                "pattern": name,
                "severity": severity,
                "snippet": _snippet(text, match),
            })
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
                        abs(match.start() - orig_start) < 10
                        for orig_start, _orig_end in original_hits[name]
                    )
                    if already_found:
                        continue
                matches.append({
                    "pattern": f"homoglyph:{name}",
                    "severity": severity,
                    "snippet": _snippet(normalized, match),
                })

    # Phase 3: Decode-and-scan (base64 and hex)
    matches.extend(_scan_decoded(text, _BASE64_RE, _decode_base64, "base64_decoded"))
    matches.extend(_scan_decoded(text, _HEX_RE, _decode_hex, "hex_decoded"))

    # Determine risk level
    if not matches:
        risk = RISK_OK
    elif any(m["severity"] == SEVERITY_HIGH for m in matches):
        risk = RISK_HIGH
    else:
        risk = RISK_MEDIUM

    return {"risk": risk, "matches": matches}
