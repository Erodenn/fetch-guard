"""Content type detection and non-HTML content handling.

Classifies HTTP Content-Type headers and converts non-HTML content
(JSON, XML/RSS, CSV, plain text, markdown) into LLM-ready markdown.
"""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET

# Content class constants — used in classify() returns, handle() dispatch,
# and pipeline.py comparisons.
CLASS_HTML = "html"
CLASS_JSON = "json"
CLASS_XML = "xml"
CLASS_CSV = "csv"
CLASS_BINARY = "binary"
CLASS_UNKNOWN = "unknown"
CLASS_PLAIN_TEXT = "plain_text"
CLASS_MARKDOWN = "markdown"

# MIME type prefix → content class
_MIME_MAP = {
    "text/html": CLASS_HTML,
    "application/xhtml+xml": CLASS_HTML,
    "text/plain": CLASS_PLAIN_TEXT,
    "text/markdown": CLASS_MARKDOWN,
    "text/x-markdown": CLASS_MARKDOWN,
    "application/json": CLASS_JSON,
    "text/json": CLASS_JSON,
    "application/xml": CLASS_XML,
    "text/xml": CLASS_XML,
    "application/rss+xml": CLASS_XML,
    "application/atom+xml": CLASS_XML,
    "application/rdf+xml": CLASS_XML,
    "text/csv": CLASS_CSV,
    "application/csv": CLASS_CSV,
}

_BINARY_PREFIXES = (
    "image/",
    "audio/",
    "video/",
    "application/octet-stream",
    "application/pdf",
    "application/zip",
    "application/gzip",
    "application/x-tar",
    "application/vnd.",
)

_HTML_SNIFF_RE = re.compile(r"^\s*(<\!doctype\s+html|<html[\s>])", re.IGNORECASE)


def _parse_mime(content_type_header):
    """Extract the MIME type from a Content-Type header, stripping params."""
    if not content_type_header:
        return ""
    return content_type_header.split(";")[0].strip().lower()


def classify(content_type_header, body_preview=""):
    """Classify a Content-Type header into a content class.

    Args:
        content_type_header: Raw Content-Type header string.
        body_preview: First ~500 chars of the response body, used for
            sniffing text/plain that is actually HTML.

    Returns:
        One of: "html", "plain_text", "markdown", "json", "xml", "csv",
        "binary", or "unknown".
    """
    mime = _parse_mime(content_type_header)

    if not mime:
        return CLASS_UNKNOWN

    # Direct lookup
    content_class = _MIME_MAP.get(mime)

    if content_class is None:
        # Check binary prefixes
        for prefix in _BINARY_PREFIXES:
            if mime.startswith(prefix):
                return CLASS_BINARY
        return CLASS_UNKNOWN

    # Sniff text/plain for HTML
    if content_class == CLASS_PLAIN_TEXT and body_preview and _HTML_SNIFF_RE.search(body_preview[:200]):
        return CLASS_HTML

    return content_class


def _handle_json(raw_body):
    """Format JSON content as a fenced code block."""
    try:
        parsed = json.loads(raw_body)
        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        formatted = raw_body
    return f"```json\n{formatted}\n```"


_FEED_SNIFF_RE = re.compile(r"<(?:\w+:)?(?:rss|feed)[\s>]", re.IGNORECASE)


def _strip_ns(tag):
    """Remove XML namespace prefix from a tag."""
    return re.sub(r"\{[^}]+\}", "", tag)


def _handle_xml(raw_body):
    """Parse XML — render RSS/Atom feeds as markdown, else fenced block."""
    # Sniff for feed tags before expensive parse — most XML isn't RSS/Atom
    if not _FEED_SNIFF_RE.search(raw_body[:500]):
        return f"```xml\n{raw_body}\n```"

    try:
        root = ET.fromstring(raw_body)  # noqa: S314
    except ET.ParseError:
        return f"```xml\n{raw_body}\n```"

    # Strip namespace for easier tag matching
    tag = _strip_ns(root.tag).lower()

    if tag == "rss":
        return _render_feed(root, _RSS_CONFIG)
    if tag == "feed":
        return _render_feed(root, _ATOM_CONFIG)

    # Matched sniff but root tag isn't rss/feed (e.g. nested element)
    return f"```xml\n{raw_body}\n```"


def _find_child_text(element, local_name):
    """Find text of a direct child by local name, ignoring namespace."""
    for child in element:
        if _strip_ns(child.tag).lower() == local_name.lower():
            return (child.text or "").strip()
    return ""


def _find_child_attr(element, local_name, attr):
    """Find an attribute of a direct child by local name, ignoring namespace."""
    for child in element:
        if _strip_ns(child.tag).lower() == local_name.lower():
            return child.get(attr, "")
    return ""


_RSS_CONFIG = {
    "container_tag": "channel",
    "item_tag": "item",
    "subtitle_tag": "description",
    "description_tags": ["description"],
    "link_mode": "text",
}

_ATOM_CONFIG = {
    "container_tag": None,
    "item_tag": "entry",
    "subtitle_tag": "subtitle",
    "description_tags": ["summary", "content"],
    "link_mode": "attr",
}


def _render_feed(root, config):
    """Render RSS or Atom feed as markdown using a format config."""
    # RSS wraps items in <channel>; Atom uses root directly
    if config["container_tag"]:
        container = None
        for child in root:
            if _strip_ns(child.tag).lower() == config["container_tag"]:
                container = child
                break
        if container is None:
            return f"```xml\n{ET.tostring(root, encoding='unicode')}\n```"
    else:
        container = root

    lines = []

    title = _find_child_text(container, "title")
    if title:
        lines.append(f"# {title}\n")

    subtitle = _find_child_text(container, config["subtitle_tag"])
    if subtitle:
        lines.append(f"{subtitle}\n")

    for item in container:
        if _strip_ns(item.tag).lower() != config["item_tag"]:
            continue
        item_title = _find_child_text(item, "title")

        # RSS: link text is the URL; Atom: link href attribute is the URL
        if config["link_mode"] == "text":
            item_link = _find_child_text(item, "link")
        else:
            item_link = _find_child_attr(item, "link", "href")

        if item_title and item_link:
            lines.append(f"## [{item_title}]({item_link})\n")
        elif item_title:
            lines.append(f"## {item_title}\n")

        # Use first available description tag
        for desc_tag in config["description_tags"]:
            desc = _find_child_text(item, desc_tag)
            if desc:
                lines.append(f"{desc}\n")
                break

    return "\n".join(lines).strip()


MAX_CSV_ROWS = 2000


def _handle_csv(raw_body):
    """Convert CSV to a markdown table (capped at MAX_CSV_ROWS data rows)."""
    try:
        reader = csv.reader(io.StringIO(raw_body))
        header = next(reader, None)
    except csv.Error:
        return raw_body

    if not header:
        return raw_body

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row_count, row in enumerate(reader):
        if row_count >= MAX_CSV_ROWS:
            lines.append(f"\n*({MAX_CSV_ROWS} row limit reached — output truncated)*")
            break
        # Pad or trim to match header width
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")

    return "\n".join(lines)


def handle(content_class, raw_body):
    """Convert non-HTML body to LLM-ready markdown.

    Args:
        content_class: The content class from classify().
        raw_body: The raw response body text.

    Returns:
        Formatted markdown string, or None for binary content.
    """
    if content_class == CLASS_BINARY:
        return None
    if content_class == CLASS_JSON:
        return _handle_json(raw_body)
    if content_class == CLASS_XML:
        return _handle_xml(raw_body)
    if content_class == CLASS_CSV:
        return _handle_csv(raw_body)
    # plain_text, markdown, unknown — return as-is
    return raw_body
