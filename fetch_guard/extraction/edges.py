"""Edge case detection — classifies fetch results for bot blocks, paywalls, and login walls."""

import re

# Edge type constants
EDGE_BOT_BLOCK = "bot_block"
EDGE_PAYWALL = "paywall"
EDGE_LOGIN_WALL = "login_wall"

# Confidence levels
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"

# ---------------------------------------------------------------------------
# Compiled detection patterns
# ---------------------------------------------------------------------------

_CLOUDFLARE_PATTERNS = re.compile(
    r"cf-browser-verification|__cf_chl_|cf-challenge|"
    r"data-cfasync|cf-turnstile|Just a moment\.\.\.",
    re.IGNORECASE,
)

_GENERIC_BOT_BLOCK_PATTERNS = re.compile(
    r"access\s+denied|blocked|suspicious\s+activity|"
    r"automated\s+access|bot\s+detected|"
    r"please\s+verify\s+you\s+are\s+human|"
    r"enable\s+javascript\s+and\s+cookies",
    re.IGNORECASE,
)

_PAYWALL_PATTERNS = re.compile(
    r"subscribe\s+to\s+continue|subscription\s+required|"
    r"paywall[-_]overlay|premium\s+content|"
    r"start\s+your\s+free\s+trial|"
    r"already\s+a\s+subscriber",
    re.IGNORECASE,
)

_LOGIN_WALL_PATTERNS = re.compile(
    r"sign\s+in\s+to\s+continue|log\s+in\s+to\s+continue|"
    r"members\s+only|create\s+an?\s+account\s+to\s+continue|"
    r"please\s+log\s+in",
    re.IGNORECASE,
)

_LOGIN_URL_PATTERNS = re.compile(
    r"/login|/signin|/sign-in|/auth",
    re.IGNORECASE,
)

# Status codes that suggest bot blocking
# Status codes that suggest bot blocking (999 = LinkedIn custom denial)
_BOT_BLOCK_STATUSES = {401, 403, 429, 503, 999}


def detect(fetch_result):
    """Classify a fetch result for edge case conditions.

    Args:
        fetch_result: dict with status_code, html, final_url, error

    Returns:
        dict with:
            edge_type: "bot_block" | "paywall" | "login_wall" | None
            confidence: "high" | "medium" | None
            detail: human-readable description or None
            should_retry: True only for bot_block (retry with browser UA)
    """
    status = fetch_result.get("status_code")
    html = fetch_result.get("html") or ""
    final_url = fetch_result.get("final_url") or ""

    # --- Bot block detection ---
    if status in _BOT_BLOCK_STATUSES:
        if status == 429:
            return {
                "edge_type": EDGE_BOT_BLOCK,
                "confidence": CONFIDENCE_HIGH,
                "detail": "Rate limited (HTTP 429)",
                "should_retry": True,
            }

        if _CLOUDFLARE_PATTERNS.search(html):
            return {
                "edge_type": EDGE_BOT_BLOCK,
                "confidence": CONFIDENCE_HIGH,
                "detail": "Cloudflare challenge detected",
                "should_retry": True,
            }

        if _GENERIC_BOT_BLOCK_PATTERNS.search(html):
            return {
                "edge_type": EDGE_BOT_BLOCK,
                "confidence": CONFIDENCE_MEDIUM,
                "detail": f"Bot block pattern detected (HTTP {status})",
                "should_retry": True,
            }

        # Bare 401/403/999 without recognizable body patterns
        if status in {401, 403, 999}:
            return {
                "edge_type": EDGE_BOT_BLOCK,
                "confidence": CONFIDENCE_MEDIUM,
                "detail": f"Access denied (HTTP {status})",
                "should_retry": True,
            }

    # --- Paywall detection (any status, typically 200) ---
    if _PAYWALL_PATTERNS.search(html):
        return {
            "edge_type": EDGE_PAYWALL,
            "confidence": CONFIDENCE_MEDIUM,
            "detail": "Paywall pattern detected",
            "should_retry": False,
        }

    # --- Login wall detection ---
    if _LOGIN_WALL_PATTERNS.search(html):
        return {
            "edge_type": EDGE_LOGIN_WALL,
            "confidence": CONFIDENCE_MEDIUM,
            "detail": "Login wall pattern detected",
            "should_retry": False,
        }

    if _LOGIN_URL_PATTERNS.search(final_url):
        return {
            "edge_type": EDGE_LOGIN_WALL,
            "confidence": CONFIDENCE_MEDIUM,
            "detail": "Redirected to login page",
            "should_retry": False,
        }

    # --- No edge case ---
    return {
        "edge_type": None,
        "confidence": None,
        "detail": None,
        "should_retry": False,
    }
