"""External link extraction from HTML."""

from collections import defaultdict
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def _is_external(href, source_domain):
    """Check if a URL is external (different domain from source)."""
    try:
        parsed = urlparse(href)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    return parsed.netloc.lower() != source_domain.lower()


def _parse_links(html, source_url, soup=None):
    """Parse all external links from HTML. Returns list of (url, anchor, domain) tuples."""
    source_domain = urlparse(source_url).netloc
    if soup is None:
        soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not _is_external(href, source_domain):
            continue
        anchor = a.get_text(strip=True) or ""
        domain = urlparse(href).netloc.lower()
        links.append((href, anchor, domain))
    return links


def extract_domains(html, source_url, soup=None):
    """Return a sorted list of unique external domains from HTML links."""
    links = _parse_links(html, source_url, soup=soup)
    domains = {domain for _, _, domain in links}
    return sorted(domains)


def extract_full(html, source_url, soup=None):
    """Return external links grouped by domain.

    Returns a dict: {domain: [{url, anchor}, ...], ...}
    Domains are sorted, links within each domain are in document order.
    """
    links = _parse_links(html, source_url, soup=soup)
    grouped = defaultdict(list)
    for url, anchor, domain in links:
        grouped[domain].append({"url": url, "anchor": anchor})
    return dict(sorted(grouped.items()))
