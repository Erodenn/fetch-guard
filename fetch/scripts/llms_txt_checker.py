"""Preflight check for /llms.txt at the domain root."""

from urllib.parse import urlparse

import requests

from fetch_client import USER_AGENT

MAX_TIMEOUT = 5


def _domain_root(url):
    """Extract the domain root URL (scheme + netloc)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_root_url(url):
    """Check if the URL points to a domain root (no meaningful path)."""
    parsed = urlparse(url)
    return parsed.path in ("", "/")


def check(url, timeout=5):
    """HEAD then GET for /llms.txt at the domain root.

    Args:
        url: any URL — the domain root is extracted automatically
        timeout: request timeout in seconds (capped at MAX_TIMEOUT)

    Returns a dict with:
        available: bool
        content: str or None
        url: the /llms.txt URL or None
    """
    timeout = min(timeout, MAX_TIMEOUT)
    root = _domain_root(url)
    llms_url = f"{root}/llms.txt"
    headers = {"User-Agent": USER_AGENT}

    try:
        head = requests.head(llms_url, timeout=timeout, headers=headers, allow_redirects=True)
        if head.status_code != 200:
            return {"available": False, "content": None, "url": None}
    except requests.RequestException:
        return {"available": False, "content": None, "url": None}

    try:
        get = requests.get(llms_url, timeout=timeout, headers=headers, allow_redirects=True)
        if get.status_code != 200 or not get.text.strip():
            return {"available": False, "content": None, "url": None}
        get.encoding = get.apparent_encoding or "utf-8"
        return {"available": True, "content": get.text, "url": llms_url}
    except requests.RequestException:
        return {"available": False, "content": None, "url": None}
