"""HTTP fetch layer — requests wrapper with timeout, User-Agent, and redirect handling."""

import requests

USER_AGENT = "Mozilla/5.0 (compatible; ClaudeFetch/1.0)"


def fetch(url, timeout=180):
    """Fetch a URL and return the result.

    Returns a dict with:
        status_code: int or None on error
        html: response body text or None
        final_url: after redirects
        error: error message string or None
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
            allow_redirects=True,
        )
        response.raise_for_status()
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
    except requests.exceptions.HTTPError as e:
        return {
            "status_code": e.response.status_code if e.response else None,
            "html": None,
            "final_url": url,
            "error": f"HTTP {e.response.status_code}: {e}" if e.response else str(e),
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": str(e),
        }
