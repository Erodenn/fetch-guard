"""Tests for content_extractor module."""

from unittest.mock import patch

from fetch_guard.extraction import content as content_extractor


class TestExtract:
    """Tests for content_extractor.extract()."""

    @patch("fetch_guard.extraction.content.trafilatura.extract")
    def test_returns_markdown(self, mock_extract):
        mock_extract.return_value = "# Title\n\nSome article content."
        result = content_extractor.extract("<html><body><article>content</article></body></html>")
        assert result == "# Title\n\nSome article content."

    @patch("fetch_guard.extraction.content.trafilatura.extract")
    def test_returns_none_on_empty(self, mock_extract):
        mock_extract.return_value = ""
        result = content_extractor.extract("<html></html>")
        assert result is None

    @patch("fetch_guard.extraction.content.trafilatura.extract")
    def test_returns_none_on_whitespace_only(self, mock_extract):
        mock_extract.return_value = "   \n  "
        result = content_extractor.extract("<html></html>")
        assert result is None

    @patch("fetch_guard.extraction.content.trafilatura.extract")
    def test_returns_none_when_trafilatura_returns_none(self, mock_extract):
        mock_extract.return_value = None
        result = content_extractor.extract("<html></html>")
        assert result is None

    @patch("fetch_guard.extraction.content.trafilatura.extract")
    def test_passes_markdown_format(self, mock_extract):
        mock_extract.return_value = "content"
        content_extractor.extract("<html></html>")
        _, kwargs = mock_extract.call_args
        assert kwargs["output_format"] == "markdown"
        assert kwargs["include_links"] is True
