"""Tests for fetch_client module."""

from unittest.mock import MagicMock, patch

import requests

import fetch_client


class TestFetch:
    """Tests for fetch_client.fetch()."""

    @patch("fetch_client.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello</body></html>"
        mock_response.url = "https://example.com"
        mock_response.apparent_encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_client.fetch("https://example.com")

        assert result["status_code"] == 200
        assert result["html"] == "<html><body>Hello</body></html>"
        assert result["final_url"] == "https://example.com"
        assert result["error"] is None

    @patch("fetch_client.requests.get")
    def test_redirect_captures_final_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_response.url = "https://example.com/final"
        mock_response.apparent_encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_client.fetch("https://example.com/redirect")

        assert result["final_url"] == "https://example.com/final"

    @patch("fetch_client.requests.get")
    def test_timeout_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()

        result = fetch_client.fetch("https://example.com", timeout=5)

        assert result["status_code"] is None
        assert result["html"] is None
        assert "timed out" in result["error"]
        assert result["final_url"] == "https://example.com"

    @patch("fetch_client.requests.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")

        result = fetch_client.fetch("https://nonexistent.test")

        assert result["status_code"] is None
        assert "Connection error" in result["error"]

    @patch("fetch_client.requests.get")
    def test_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = requests.exceptions.HTTPError(response=mock_response)
        mock_get.side_effect = error

        result = fetch_client.fetch("https://example.com/missing")

        assert result["status_code"] == 404
        assert "404" in result["error"]

    @patch("fetch_client.requests.get")
    def test_custom_timeout_passed(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.url = "https://example.com"
        mock_response.apparent_encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetch_client.fetch("https://example.com", timeout=30)

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 30

    @patch("fetch_client.requests.get")
    def test_user_agent_header(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.url = "https://example.com"
        mock_response.apparent_encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetch_client.fetch("https://example.com")

        _, kwargs = mock_get.call_args
        assert "ClaudeFetch" in kwargs["headers"]["User-Agent"]
