"""HTTP fetch layer — requests wrapper with timeout, User-Agent, and redirect handling."""

import requests

USER_AGENT = "Mozilla/5.0 (compatible; ClaudeFetch/1.0)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def fetch(url, timeout=180, user_agent=None):
    """Fetch a URL and return the result.

    Returns a dict with:
        status_code: int or None on error
        html: response body text or None
        final_url: after redirects
        error: error message string or None

    Non-2xx responses return the body in html (for edge case detection).
    Only connection-level failures set error.
    """
    ua = user_agent or USER_AGENT
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
            allow_redirects=True,
        )
        response.encoding = response.apparent_encoding or "utf-8"
        return {
            "status_code": response.status_code,
            "html": response.text,
            "final_url": response.url,
            "error": None,
        }
    except requests.exceptions.Timeout:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": f"Request timed out after {timeout} seconds",
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": f"Connection error: {e}",
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": str(e),
        }
