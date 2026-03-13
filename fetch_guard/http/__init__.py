"""HTTP fetching layer — static requests, Playwright JS rendering, and llms.txt preflight."""

from .client import BROWSER_USER_AGENT, USER_AGENT
from .client import fetch as static_fetch
from .llms_txt import check as check_llms_txt
from .llms_txt import is_root_url
from .playwright import fetch as playwright_fetch

__all__ = [
    "BROWSER_USER_AGENT",
    "USER_AGENT",
    "check_llms_txt",
    "is_root_url",
    "playwright_fetch",
    "static_fetch",
]
