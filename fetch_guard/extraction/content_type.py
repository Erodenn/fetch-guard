"""Content type detection and non-HTML content handling.

Classifies HTTP Content-Type headers and converts non-HTML content
(JSON, XML/RSS, CSV, plain text, markdown) into LLM-ready markdown.
"""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET

# MIME type prefix → content class
_MIME_MAP = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/plain": "plain_text",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "application/json": "json",
    "text/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/rss+xml": "xml",
    "application/atom+xml": "xml",
    "application/rdf+xml": "xml",
    "text/csv": "csv",
    "application/csv": "csv",
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
        return "unknown"

    # Direct lookup
    content_class = _MIME_MAP.get(mime)

    if content_class is None:
        # Check binary prefixes
        for prefix in _BINARY_PREFIXES:
            if mime.startswith(prefix):
                return "binary"
        return "unknown"

    # Sniff text/plain for HTML
    if content_class == "plain_text" and body_preview and _HTML_SNIFF_RE.search(body_preview[:200]):
        return "html"

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
        return _render_rss(root)
    if tag == "feed":
        return _render_atom(root)

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


def _render_rss(root):
    """Render RSS feed items as markdown."""
    lines = []
    channel = None
    for child in root:
        if _strip_ns(child.tag).lower() == "channel":
            channel = child
            break

    if channel is None:
        return f"```xml\n{ET.tostring(root, encoding='unicode')}\n```"

    title = _find_child_text(channel, "title")
    if title:
        lines.append(f"# {title}\n")

    description = _find_child_text(channel, "description")
    if description:
        lines.append(f"{description}\n")

    for item in channel:
        if _strip_ns(item.tag).lower() != "item":
            continue
        item_title = _find_child_text(item, "title")
        item_link = _find_child_text(item, "link")
        item_desc = _find_child_text(item, "description")

        if item_title and item_link:
            lines.append(f"## [{item_title}]({item_link})\n")
        elif item_title:
            lines.append(f"## {item_title}\n")

        if item_desc:
            lines.append(f"{item_desc}\n")

    return "\n".join(lines).strip()


def _render_atom(root):
    """Render Atom feed entries as markdown."""
    lines = []

    title = _find_child_text(root, "title")
    if title:
        lines.append(f"# {title}\n")

    subtitle = _find_child_text(root, "subtitle")
    if subtitle:
        lines.append(f"{subtitle}\n")

    for entry in root:
        if _strip_ns(entry.tag).lower() != "entry":
            continue
        entry_title = _find_child_text(entry, "title")
        entry_link = _find_child_attr(entry, "link", "href")
        entry_summary = _find_child_text(entry, "summary")
        entry_content = _find_child_text(entry, "content")

        if entry_title and entry_link:
            lines.append(f"## [{entry_title}]({entry_link})\n")
        elif entry_title:
            lines.append(f"## {entry_title}\n")

        if entry_summary:
            lines.append(f"{entry_summary}\n")
        elif entry_content:
            lines.append(f"{entry_content}\n")

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
    if content_class == "binary":
        return None
    if content_class == "json":
        return _handle_json(raw_body)
    if content_class == "xml":
        return _handle_xml(raw_body)
    if content_class == "csv":
        return _handle_csv(raw_body)
    # plain_text, markdown, unknown — return as-is
    return raw_body
