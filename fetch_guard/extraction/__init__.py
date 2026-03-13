"""Content extraction — article body, links, metadata, content-type routing, and edge detection."""

from .content import extract as extract_content
from .content_type import classify as classify_content_type
from .content_type import handle as handle_content_type
from .edges import detect as detect_edges
from .links import extract_domains, extract_full
from .metadata import extract as extract_metadata
from .metadata import null_metadata

__all__ = [
    "classify_content_type",
    "detect_edges",
    "extract_content",
    "extract_domains",
    "extract_full",
    "extract_metadata",
    "handle_content_type",
    "null_metadata",
]
