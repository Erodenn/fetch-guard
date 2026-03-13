"""Tests for llms_txt_checker module."""

from unittest.mock import MagicMock, patch

from fetch_guard.http import llms_txt as llms_txt_checker


class TestDomainRoot:
    """Tests for domain root extraction."""

    def test_simple_url(self):
        assert llms_txt_checker._domain_root("https://example.com/page") == "https://example.com"

    def test_with_port(self):
        assert llms_txt_checker._domain_root("https://example.com:8080/path") == "https://example.com:8080"

    def test_root_url(self):
        assert llms_txt_checker._domain_root("https://example.com/") == "https://example.com"

    def test_http_scheme(self):
        assert llms_txt_checker._domain_root("http://example.com/page") == "http://example.com"


class TestIsRootUrl:
    """Tests for is_root_url detection."""

    def test_root_with_slash(self):
        assert llms_txt_checker.is_root_url("https://example.com/") is True

    def test_root_without_slash(self):
        assert llms_txt_checker.is_root_url("https://example.com") is True

    def test_non_root(self):
        assert llms_txt_checker.is_root_url("https://example.com/page") is False

    def test_deep_path(self):
        assert llms_txt_checker.is_root_url("https://example.com/a/b/c") is False


class TestCheck:
    """Tests for llms_txt_checker.check()."""

    @patch("fetch_guard.http.llms_txt.requests")
    def test_available(self, mock_requests):
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.text = "# llms.txt\nThis site is about testing."
        get_resp.apparent_encoding = "utf-8"

        mock_requests.get.return_value = get_resp
        mock_requests.RequestException = Exception

        result = llms_txt_checker.check("https://example.com/page")
        assert result["available"] is True
        assert result["content"] == "# llms.txt\nThis site is about testing."
        assert result["url"] == "https://example.com/llms.txt"

    @patch("fetch_guard.http.llms_txt.requests")
    def test_not_found(self, mock_requests):
        get_resp = MagicMock()
        get_resp.status_code = 404

        mock_requests.get.return_value = get_resp
        mock_requests.RequestException = Exception

        result = llms_txt_checker.check("https://example.com")
        assert result["available"] is False
        assert result["content"] is None

    @patch("fetch_guard.http.llms_txt.requests")
    def test_request_error(self, mock_requests):
        mock_requests.get.side_effect = Exception("timeout")
        mock_requests.RequestException = Exception

        result = llms_txt_checker.check("https://example.com")
        assert result["available"] is False

    @patch("fetch_guard.http.llms_txt.requests")
    def test_empty_content(self, mock_requests):
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.text = "   "
        get_resp.apparent_encoding = "utf-8"

        mock_requests.get.return_value = get_resp
        mock_requests.RequestException = Exception

        result = llms_txt_checker.check("https://example.com")
        assert result["available"] is False

    @patch("fetch_guard.http.llms_txt.requests")
    def test_timeout_capped(self, mock_requests):
        get_resp = MagicMock()
        get_resp.status_code = 404
        mock_requests.get.return_value = get_resp
        mock_requests.RequestException = Exception

        llms_txt_checker.check("https://example.com", timeout=60)
        # Should be capped to MAX_TIMEOUT (5s)
        mock_requests.get.assert_called_once()
        call_kwargs = mock_requests.get.call_args[1]
        assert call_kwargs["timeout"] == 5
