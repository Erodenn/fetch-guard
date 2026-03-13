"""Pre-extraction HTML sanitizer — removes hidden content vectors before trafilatura processes the page."""

import re
import unicodedata

from bs4 import BeautifulSoup

# CSS patterns for hidden/off-screen elements
HIDDEN_STYLE_PATTERNS = [
    re.compile(r"display\s*:\s*none", re.IGNORECASE),
    re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE),
    re.compile(r"opacity\s*:\s*0(?:[;\s]|$)", re.IGNORECASE),
]

OFFSCREEN_STYLE_PATTERNS = [
    re.compile(
        r"position\s*:\s*(?:absolute|fixed)"
        r".*?"
        r"(?:left|top|right|bottom)\s*:\s*-\d{3,}",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Non-printing unicode categories and specific codepoints to strip
NONPRINTING_CODEPOINTS = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\u202a",  # left-to-right embedding
    "\u202b",  # right-to-left embedding
    "\u202c",  # pop directional formatting
    "\u202d",  # left-to-right override
    "\u202e",  # right-to-left override
    "\u2060",  # word joiner
    "\u2061",  # function application
    "\u2062",  # invisible times
    "\u2063",  # invisible separator
    "\u2064",  # invisible plus
    "\ufeff",  # byte order mark (zero-width no-break space)
    "\ufff9",  # interlinear annotation anchor
    "\ufffa",  # interlinear annotation separator
    "\ufffb",  # interlinear annotation terminator
}


def _is_decomposed(element):
    """Check if a BeautifulSoup element has been decomposed."""
    return element.attrs is None


def _matches_style_patterns(element, patterns):
    """Check if an element's inline style matches any pattern in the list."""
    if _is_decomposed(element):
        return False
    style = element.get("style", "")
    if not style:
        return False
    return any(p.search(style) for p in patterns)


def _strip_nonprinting(text):
    """Remove non-printing unicode characters. Returns (cleaned_text, count_removed)."""
    count = 0
    chars = []
    for ch in text:
        if (ch in NONPRINTING_CODEPOINTS or unicodedata.category(ch) in ("Cf", "Cc")) and ch not in ("\n", "\r", "\t"):
            count += 1
        else:
            chars.append(ch)
    return "".join(chars), count


def sanitize(html):
    """Remove hidden content vectors from HTML.

    Returns (cleaned_html_string, soup, tally_dict).
    soup is the sanitized BeautifulSoup tree (before non-printing char strip),
    suitable for reuse by metadata and link extractors.
    tally_dict has keys: hidden_elements, offscreen_elements, nonprinting_chars.
    """
    soup = BeautifulSoup(html, "html.parser")
    tally = {
        "hidden_elements": 0,
        "offscreen_elements": 0,
        "nonprinting_chars": 0,
    }

    # Remove elements with hidden or off-screen inline styles (single pass)
    for element in list(soup.find_all(style=True)):
        if _matches_style_patterns(element, HIDDEN_STYLE_PATTERNS):
            element.decompose()
            tally["hidden_elements"] += 1
        elif _matches_style_patterns(element, OFFSCREEN_STYLE_PATTERNS):
            element.decompose()
            tally["offscreen_elements"] += 1

    # Remove aria-hidden elements
    for element in list(soup.find_all(attrs={"aria-hidden": "true"})):
        element.decompose()
        tally["hidden_elements"] += 1

    # Remove <noscript> tags
    for element in list(soup.find_all("noscript")):
        element.decompose()
        tally["hidden_elements"] += 1

    # Snapshot the sanitized soup before string conversion — metadata and link
    # extractors can reuse this instead of re-parsing.
    sanitized_soup = soup

    cleaned_html = str(soup)

    # Strip non-printing unicode from the HTML string
    cleaned_html, nonprinting_count = _strip_nonprinting(cleaned_html)
    tally["nonprinting_chars"] = nonprinting_count

    return cleaned_html, sanitized_soup, tally
