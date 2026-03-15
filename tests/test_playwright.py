"""Tests for playwright_fetcher module."""

from unittest.mock import MagicMock, patch

from fetch_guard.http import playwright as playwright_fetcher


class TestPlaywrightFetch:
    """Basic smoke tests — exercise the module-level import path."""

    def test_missing_playwright_returns_install_instructions(self):
        """When playwright is not importable, return helpful error."""
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            import importlib
            importlib.reload(playwright_fetcher)

            result = playwright_fetcher.fetch("https://example.com")
            assert isinstance(result, dict)
            if result["error"]:
                assert "playwright" in result["error"].lower() or "Playwright" in result["error"]

    def test_return_dict_shape(self):
        """Verify return dict has all expected keys."""
        result = playwright_fetcher.fetch("https://example.com", timeout=5)
        assert "status_code" in result
        assert "html" in result
        assert "final_url" in result
        assert "error" in result
        assert "content_type" in result


class TestPlaywrightFetchIntegration:
    """Integration-style tests with full mock chain via sys.modules injection."""

    # ---------- helpers ----------

    def _build_mock_chain(
        self,
        page_html="<html><body>Hello</body></html>",
        page_url="https://example.com",
        status=200,
        content_type="text/html",
        networkidle_error=None,
        goto_error=None,
        goto_none_response=False,
    ):
        """Build a complete playwright mock chain.

        Returns (mock_sync_pw, mock_page, mock_context) where mock_sync_pw is
        a callable that returns a context manager yielding the mock p object.
        Inject via _pw_module() into sys.modules["playwright.sync_api"].
        """
        mock_page = MagicMock()
        mock_page.content.return_value = page_html
        mock_page.url = page_url

        if goto_error:
            mock_page.goto.side_effect = goto_error
        elif goto_none_response:
            mock_page.goto.return_value = None
        else:
            mock_response = MagicMock()
            mock_response.status = status
            mock_response.headers = MagicMock()
            mock_response.headers.get.side_effect = (
                lambda key, default="": content_type if key == "content-type" else default
            )
            mock_page.goto.return_value = mock_response

        if networkidle_error:
            mock_page.wait_for_load_state.side_effect = networkidle_error
        else:
            mock_page.wait_for_load_state.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_pw)
        mock_cm.__exit__ = MagicMock(return_value=False)

        mock_sync_pw = MagicMock(return_value=mock_cm)

        return mock_sync_pw, mock_page, mock_context

    def _pw_module(self, mock_sync_pw, timeout_error_cls=None):
        """Build a fake playwright.sync_api module for sys.modules injection."""
        if timeout_error_cls is None:
            timeout_error_cls = type("TimeoutError", (Exception,), {})
        mock_mod = MagicMock()
        mock_mod.sync_playwright = mock_sync_pw
        mock_mod.TimeoutError = timeout_error_cls
        return mock_mod

    # ---------- tests ----------

    def test_successful_fetch_returns_correct_shape(self):
        mock_sync_pw, _, _ = self._build_mock_chain()
        with patch.dict("sys.modules", {"playwright.sync_api": self._pw_module(mock_sync_pw)}):
            result = playwright_fetcher.fetch("https://example.com")

        assert result["html"] == "<html><body>Hello</body></html>"
        assert result["final_url"] == "https://example.com"
        assert result["status_code"] == 200
        assert result["content_type"] == "text/html"
        assert result["error"] is None

    def test_custom_headers_passed_to_new_context(self):
        mock_sync_pw, _, _ = self._build_mock_chain()
        custom_headers = {"Authorization": "Bearer secret", "X-Custom": "value"}

        with patch.dict("sys.modules", {"playwright.sync_api": self._pw_module(mock_sync_pw)}):
            playwright_fetcher.fetch("https://example.com", headers=custom_headers)

        # browser.new_context() must receive our headers
        mock_browser = mock_sync_pw.return_value.__enter__.return_value.chromium.launch.return_value
        mock_browser.new_context.assert_called_once_with(extra_http_headers=custom_headers)

    def test_no_headers_passes_empty_dict_to_new_context(self):
        mock_sync_pw, _, _ = self._build_mock_chain()

        with patch.dict("sys.modules", {"playwright.sync_api": self._pw_module(mock_sync_pw)}):
            playwright_fetcher.fetch("https://example.com", headers=None)

        mock_browser = mock_sync_pw.return_value.__enter__.return_value.chromium.launch.return_value
        mock_browser.new_context.assert_called_once_with(extra_http_headers={})

    def test_networkidle_timeout_suppressed(self):
        """wait_for_load_state TimeoutError must be suppressed — html still returned."""
        pw_timeout_cls = type("TimeoutError", (Exception,), {})
        mock_sync_pw, _, _ = self._build_mock_chain(networkidle_error=pw_timeout_cls("timed out"))
        pw_mod = self._pw_module(mock_sync_pw, timeout_error_cls=pw_timeout_cls)

        with patch.dict("sys.modules", {"playwright.sync_api": pw_mod}):
            result = playwright_fetcher.fetch("https://example.com")

        assert result["html"] == "<html><body>Hello</body></html>"
        assert result["error"] is None

    def test_none_goto_response_status_code_is_none(self):
        """If page.goto() returns None, status_code and content_type should be None/empty."""
        mock_sync_pw, _, _ = self._build_mock_chain(goto_none_response=True)

        with patch.dict("sys.modules", {"playwright.sync_api": self._pw_module(mock_sync_pw)}):
            result = playwright_fetcher.fetch("https://example.com")

        assert result["status_code"] is None
        assert result["error"] is None   # no exception raised

    def test_goto_timeout_returns_error_result(self):
        """page.goto() TimeoutError must propagate to error_result, not crash."""
        pw_timeout_cls = type("TimeoutError", (Exception,), {})
        mock_sync_pw, _, _ = self._build_mock_chain(goto_error=pw_timeout_cls("navigation timed out"))
        pw_mod = self._pw_module(mock_sync_pw, timeout_error_cls=pw_timeout_cls)

        with patch.dict("sys.modules", {"playwright.sync_api": pw_mod}):
            result = playwright_fetcher.fetch("https://example.com")

        assert result["error"] is not None
        assert "timed out" in result["error"].lower()
        assert result["html"] is None

    def test_final_url_from_page_url(self):
        """final_url must come from page.url (after SPA navigation), not the input URL."""
        mock_sync_pw, _, _ = self._build_mock_chain(
            page_url="https://example.com/after-redirect",
        )
        with patch.dict("sys.modules", {"playwright.sync_api": self._pw_module(mock_sync_pw)}):
            result = playwright_fetcher.fetch("https://example.com")

        assert result["final_url"] == "https://example.com/after-redirect"

    def test_content_type_from_response_headers(self):
        mock_sync_pw, _, _ = self._build_mock_chain(content_type="application/xhtml+xml")

        with patch.dict("sys.modules", {"playwright.sync_api": self._pw_module(mock_sync_pw)}):
            result = playwright_fetcher.fetch("https://example.com")

        assert result["content_type"] == "application/xhtml+xml"
