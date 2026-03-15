"""Pre-extraction HTML sanitizer — removes hidden content vectors before trafilatura processes the page."""

import re
import unicodedata

from bs4 import BeautifulSoup

# CSS patterns for hidden/off-screen elements
HIDDEN_STYLE_PATTERNS = [
    re.compile(r"display\s*:\s*none", re.IGNORECASE),
    re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE),
    re.compile(r"opacity\s*:\s*0(?:[;\s]|$)", re.IGNORECASE),
    # Extended patterns (Unit 42 2026 taxonomy)
    re.compile(r"font-size\s*:\s*0(?:px|em|rem)?\b", re.IGNORECASE),
    re.compile(
        r"color\s*:\s*(?:transparent|rgba\([^)]*,\s*0\s*\)|hsla\([^)]*,\s*0\s*\)|#[0-9a-fA-F]{6}00)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:height\s*:\s*0.+?overflow\s*:\s*hidden|overflow\s*:\s*hidden.+?height\s*:\s*0)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:max-height\s*:\s*0.+?overflow\s*:\s*hidden|overflow\s*:\s*hidden.+?max-height\s*:\s*0)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"clip\s*:\s*rect\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\)", re.IGNORECASE),
    re.compile(r"transform\s*:\s*scale\(\s*0\s*\)", re.IGNORECASE),
]

OFFSCREEN_STYLE_PATTERNS = [
    re.compile(
        r"position\s*:\s*(?:absolute|fixed)"
        r".*?"
        r"(?:left|top|right|bottom)\s*:\s*-\d{3,}",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Named color table for color-match hidden text detection (~32 CSS named colors)
_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    # Light/white-ish
    "white": (255, 255, 255), "ivory": (255, 255, 240), "snow": (255, 250, 250),
    "ghostwhite": (248, 248, 255), "floralwhite": (255, 250, 240),
    "linen": (250, 240, 230), "seashell": (255, 245, 238),
    "honeydew": (240, 255, 240), "mintcream": (245, 255, 250),
    "azure": (240, 255, 255), "aliceblue": (240, 248, 255),
    "lavender": (230, 230, 250), "lightyellow": (255, 255, 224),
    "lightcyan": (224, 255, 255), "beige": (245, 245, 220),
    "oldlace": (253, 245, 230), "cornsilk": (255, 248, 220),
    "papayawhip": (255, 239, 213), "whitesmoke": (245, 245, 245),
    "antiquewhite": (250, 235, 215),
    # Dark/black-ish
    "black": (0, 0, 0), "darkgray": (169, 169, 169), "darkgrey": (169, 169, 169),
    "dimgray": (105, 105, 105), "dimgrey": (105, 105, 105),
    "darkslategray": (47, 79, 79), "darkslategrey": (47, 79, 79),
    # Neutrals
    "silver": (192, 192, 192), "gray": (128, 128, 128), "grey": (128, 128, 128),
    "lightgray": (211, 211, 211), "lightgrey": (211, 211, 211),
}

# Compiled regexes for color-match hidden text detection
_COLOR_PROP_RE = re.compile(r"(?<![a-zA-Z-])color\s*:\s*([^;]+)", re.IGNORECASE)
_BG_COLOR_PROP_RE = re.compile(r"background-color\s*:\s*([^;]+)", re.IGNORECASE)
_HEX3_RE = re.compile(r"^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$")
_HEX6_RE = re.compile(r"^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})")
_RGB_RE = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")

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
    # Bidi isolates (category Cf — already caught by category check, explicit for documentation)
    "\u2066",  # left-to-right isolate
    "\u2067",  # right-to-left isolate
    "\u2068",  # first strong isolate
    "\u2069",  # pop directional isolate
    # Unicode Tags (category Cf — already caught by category check, explicit for documentation)
    "\U000E0001",  # language tag
    "\U000E0020",  # tag space (start of ASCII-mapped range)
    "\U000E007F",  # cancel tag
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


# Regex to extract CSS rules: selector { declarations }
_CSS_RULE_RE = re.compile(
    r"([^{}]+?)\s*\{([^}]*)\}",
    re.DOTALL,
)


def _remove_style_hidden(soup):
    """Remove elements targeted by CSS rules that hide content via <style> tags.

    Parses <style> blocks, finds rules with display:none / visibility:hidden / opacity:0,
    uses their selectors to find and decompose matching elements.
    Returns count of removed elements.
    """
    count = 0
    for style_tag in list(soup.find_all("style")):
        css_text = style_tag.string
        if not css_text:
            continue
        for selector_match in _CSS_RULE_RE.finditer(css_text):
            selector = selector_match.group(1).strip()
            declarations = selector_match.group(2)
            # Check if this rule hides content
            is_hidden = any(p.search(declarations) for p in HIDDEN_STYLE_PATTERNS)
            if not is_hidden:
                continue
            # Try each comma-separated selector independently
            for sel in selector.split(","):
                sel = sel.strip()
                if not sel:
                    continue
                try:
                    for element in list(soup.select(sel)):
                        element.decompose()
                        count += 1
                except Exception:  # noqa: S110
                    # Skip invalid/unsupported CSS selectors (e.g. pseudo-elements)
                    pass
    return count


def _parse_inline_color(value: str) -> "tuple[int, int, int] | None":
    """Parse a CSS color value to an (r, g, b) tuple, or None if unrecognized."""
    v = value.strip().lower()
    if v in _NAMED_COLORS:
        return _NAMED_COLORS[v]
    m = _HEX3_RE.match(v)
    if m:
        c1, c2, c3 = m.groups()
        return (int(c1 * 2, 16), int(c2 * 2, 16), int(c3 * 2, 16))
    m = _HEX6_RE.match(v)
    if m:
        if len(v) > 7:  # reject 8-digit hex (alpha channel present)
            return None
        h1, h2, h3 = m.groups()
        return (int(h1, 16), int(h2, 16), int(h3, 16))
    m = _RGB_RE.match(v)
    if m:
        x1, x2, x3 = m.groups()
        return (int(x1), int(x2), int(x3))
    return None


def _extract_color_pair(style: str) -> "tuple[str | None, str | None]":
    """Extract raw color and background-color values from a style attribute string."""
    cm = _COLOR_PROP_RE.search(style)
    bm = _BG_COLOR_PROP_RE.search(style)
    return (cm.group(1).strip() if cm else None,
            bm.group(1).strip() if bm else None)


def _is_color_match_hidden(element) -> bool:
    """Return True if element has matching foreground and background color (invisible text)."""
    if _is_decomposed(element):
        return False
    style = element.get("style", "")
    if not style:
        return False
    color_val, bg_val = _extract_color_pair(style)
    if color_val is None or bg_val is None:
        return False
    color_rgb = _parse_inline_color(color_val)
    bg_rgb = _parse_inline_color(bg_val)
    if color_rgb is None or bg_rgb is None:
        return False
    return color_rgb == bg_rgb


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
        elif _is_color_match_hidden(element):
            element.decompose()
            tally["hidden_elements"] += 1

    # Remove elements hidden via CSS class/ID rules in <style> tags
    tally["hidden_elements"] += _remove_style_hidden(soup)

    # Remove aria-hidden elements
    for element in list(soup.find_all(attrs={"aria-hidden": "true"})):
        element.decompose()
        tally["hidden_elements"] += 1

    # Remove <noscript> tags
    for element in list(soup.find_all("noscript")):
        element.decompose()
        tally["hidden_elements"] += 1

    # Remove <template> tags (never rendered by browsers)
    for element in list(soup.find_all("template")):
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
