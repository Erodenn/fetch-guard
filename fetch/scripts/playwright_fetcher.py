"""Playwright-based JS rendering — headless Chromium fetch for JavaScript-heavy pages."""


def fetch(url, timeout=180):
    """Fetch a URL using headless Chromium via Playwright.

    Returns the same dict shape as fetch_client.fetch():
        status_code: int or None on error
        html: rendered page HTML or None
        final_url: after redirects/SPA navigation
        error: error message string or None
    """
    try:
        from playwright.sync_api import TimeoutError as PWTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": (
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install chromium"
            ),
        }

    timeout_ms = timeout * 1000

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Try networkidle — if it times out, use whatever rendered so far
            import contextlib
            with contextlib.suppress(PWTimeoutError):
                page.wait_for_load_state("networkidle", timeout=timeout_ms)

            status_code = response.status if response else None
            html = page.content()
            final_url = page.url

            browser.close()

            return {
                "status_code": status_code,
                "html": html,
                "final_url": final_url,
                "error": None,
            }
    except PWTimeoutError:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": f"Playwright navigation timed out after {timeout} seconds",
        }
    except Exception as e:
        return {
            "status_code": None,
            "html": None,
            "final_url": url,
            "error": f"Playwright error: {e}",
        }
