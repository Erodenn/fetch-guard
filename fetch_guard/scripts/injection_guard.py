"""Session-salted tag wrapping, injection pattern scanning, and risk assessment."""

import secrets

from .injection_patterns import PATTERNS

CONTEXT_CHARS = 60

# Risk levels — use these constants instead of raw strings
RISK_OK = "OK"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

# Pattern severity levels (must match values in injection_patterns.py)
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"


def generate_salt():
    """Return an 8-char random hex string."""
    return secrets.token_hex(4)


def wrap_content(text, salt):
    """Wrap text in session-salted fetch-content tags."""
    return f"<fetch-content-{salt}>\n{text}\n</fetch-content-{salt}>"


def scan(text):
    """Scan text for injection patterns.

    Returns a dict with:
        risk: "OK", "MEDIUM", or "HIGH"
        matches: list of {pattern, severity, snippet}
    """
    matches = []
    for name, pattern, severity in PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - CONTEXT_CHARS)
            end = min(len(text), match.end() + CONTEXT_CHARS)
            snippet = text[start:end].replace("\n", " ").strip()
            matches.append({
                "pattern": name,
                "severity": severity,
                "snippet": snippet,
            })

    if not matches:
        risk = RISK_OK
    elif any(m["severity"] == SEVERITY_HIGH for m in matches):
        risk = RISK_HIGH
    else:
        risk = RISK_MEDIUM

    return {"risk": risk, "matches": matches}
