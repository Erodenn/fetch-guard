"""Structured metadata extraction — JSON-LD, Open Graph, and meta tags.

Uses extruct for JSON-LD and Open Graph, BeautifulSoup for plain meta tags.
"""

from bs4 import BeautifulSoup


def null_metadata():
    """Return the unified schema with all fields set to None."""
    return {
        "title": None,
        "author": None,
        "date": None,
        "description": None,
        "canonical_url": None,
        "image": None,
    }


def _from_json_ld(items):
    """Extract metadata from JSON-LD entries."""
    result = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if "name" in item and "title" not in result:
            result["title"] = item["name"]
        if "headline" in item and "title" not in result:
            result["title"] = item["headline"]
        if "author" in item and "author" not in result:
            author = item["author"]
            if isinstance(author, dict):
                result["author"] = author.get("name")
            elif isinstance(author, list) and author:
                first = author[0]
                result["author"] = first.get("name") if isinstance(first, dict) else str(first)
            elif isinstance(author, str):
                result["author"] = author
        if "datePublished" in item and "date" not in result:
            result["date"] = item["datePublished"]
        if "dateCreated" in item and "date" not in result:
            result["date"] = item["dateCreated"]
        if "description" in item and "description" not in result:
            result["description"] = item["description"]
        if "url" in item and "canonical_url" not in result:
            result["canonical_url"] = item["url"]
        if "image" in item and "image" not in result:
            img = item["image"]
            if isinstance(img, dict):
                result["image"] = img.get("url")
            elif isinstance(img, str):
                result["image"] = img
            elif isinstance(img, list) and img:
                first = img[0]
                result["image"] = first.get("url") if isinstance(first, dict) else str(first)
    return result


def _from_opengraph(items):
    """Extract metadata from extruct Open Graph output.

    extruct returns OG data as: [{"properties": [["og:title", "value"], ...], ...}]
    """
    result = {}
    og_mapping = {
        "og:title": "title",
        "og:description": "description",
        "og:url": "canonical_url",
        "og:image": "image",
        "article:author": "author",
        "article:published_time": "date",
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        props = item.get("properties", [])
        if not isinstance(props, list):
            continue
        for prop in props:
            if not isinstance(prop, (list, tuple)) or len(prop) < 2:
                continue
            key, value = prop[0], prop[1]
            schema_key = og_mapping.get(key)
            if schema_key and schema_key not in result:
                result[schema_key] = value
    return result


def _from_metatags(html, soup=None):
    """Extract metadata from HTML meta tags using BeautifulSoup."""
    result = {}
    if soup is None:
        soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("meta"):
        name = (tag.get("name") or "").lower()
        content = tag.get("content", "")
        if not content:
            continue
        if name == "author" and "author" not in result:
            result["author"] = content
        if name == "description" and "description" not in result:
            result["description"] = content
        if name in ("date", "pubdate", "publish_date") and "date" not in result:
            result["date"] = content
        if name == "title" and "title" not in result:
            result["title"] = content
    return result


def extract(html, soup=None):
    """Extract structured metadata from HTML.

    Args:
        html: Raw HTML string.
        soup: Optional pre-parsed BeautifulSoup tree (skips re-parsing for meta tags).

    Returns a dict with keys: title, author, date, description, canonical_url, image.
    All keys are always present; missing values are None.
    Priority: JSON-LD > OpenGraph > meta tags.
    """
    import extruct

    try:
        data = extruct.extract(html, syntaxes=["json-ld", "opengraph"])
    except Exception:
        data = {}

    # Extract from each source
    json_ld = _from_json_ld(data.get("json-ld", []))
    og = _from_opengraph(data.get("opengraph", []))
    meta = _from_metatags(html, soup=soup)

    # Merge with priority: JSON-LD > OG > meta
    merged = null_metadata()
    for key in merged:
        merged[key] = json_ld.get(key) or og.get(key) or meta.get(key)

    return merged
