"""trafilatura wrapper — extracts article body from HTML as clean markdown."""

import trafilatura


def extract(html):
    """Extract article content from HTML as markdown.

    Returns markdown string or None if extraction fails.
    """
    result = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
    )
    if not result or not result.strip():
        return None
    return result
