"""Tests for edge_detector module."""

from fetch_guard.scripts import edge_detector


def _make_result(status_code=200, html="", final_url="https://example.com"):
    return {
        "status_code": status_code,
        "html": html,
        "final_url": final_url,
        "error": None,
    }


class TestBotBlockDetection:
    """Tests for bot block edge case detection."""

    def test_cloudflare_403(self):
        result = _make_result(
            status_code=403,
            html='<div id="cf-browser-verification">Please wait...</div>',
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "bot_block"
        assert edge["confidence"] == "high"
        assert "Cloudflare" in edge["detail"]
        assert edge["should_retry"] is True

    def test_cloudflare_challenge_token(self):
        result = _make_result(
            status_code=403,
            html="<script>window.__cf_chl_opt={}</script>",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "bot_block"
        assert edge["confidence"] == "high"

    def test_cloudflare_just_a_moment(self):
        result = _make_result(
            status_code=503,
            html="<title>Just a moment...</title>",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "bot_block"
        assert "Cloudflare" in edge["detail"]

    def test_generic_403_access_denied(self):
        result = _make_result(
            status_code=403,
            html="<h1>Access Denied</h1><p>You don't have permission.</p>",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "bot_block"
        assert edge["should_retry"] is True

    def test_bare_403(self):
        result = _make_result(status_code=403, html="<html>Forbidden</html>")
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "bot_block"
        assert edge["confidence"] == "medium"

    def test_rate_limited_429(self):
        result = _make_result(status_code=429, html="Too many requests")
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "bot_block"
        assert edge["confidence"] == "high"
        assert "429" in edge["detail"]
        assert edge["should_retry"] is True

    def test_503_without_challenge_not_bot_block(self):
        result = _make_result(status_code=503, html="<h1>Service Unavailable</h1>")
        edge = edge_detector.detect(result)
        # 503 without Cloudflare markers is not classified as bot_block
        assert edge["edge_type"] is None


class TestPaywallDetection:
    """Tests for paywall edge case detection."""

    def test_subscribe_to_continue(self):
        result = _make_result(
            html="<div>Subscribe to continue reading this article</div>",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "paywall"
        assert edge["should_retry"] is False

    def test_subscription_required(self):
        result = _make_result(html="<p>Subscription required for full access</p>")
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "paywall"

    def test_paywall_overlay_class(self):
        result = _make_result(html='<div class="paywall-overlay">Sign up</div>')
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "paywall"


class TestLoginWallDetection:
    """Tests for login wall edge case detection."""

    def test_sign_in_to_continue(self):
        result = _make_result(html="<p>Sign in to continue</p>")
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "login_wall"
        assert edge["should_retry"] is False

    def test_members_only(self):
        result = _make_result(html="<h2>Members Only Content</h2>")
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "login_wall"

    def test_login_redirect(self):
        result = _make_result(
            final_url="https://example.com/login?redirect=/article",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "login_wall"
        assert "Redirected" in edge["detail"]

    def test_signin_redirect(self):
        result = _make_result(
            final_url="https://example.com/signin",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] == "login_wall"


class TestCleanResponse:
    """Tests that clean responses return no edge case."""

    def test_clean_200(self):
        result = _make_result(
            html="<html><body><h1>Hello World</h1><p>Normal content.</p></body></html>",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] is None
        assert edge["confidence"] is None
        assert edge["detail"] is None
        assert edge["should_retry"] is False

    def test_clean_200_with_article(self):
        result = _make_result(
            html="<article><h1>News Article</h1><p>Content here.</p></article>",
        )
        edge = edge_detector.detect(result)
        assert edge["edge_type"] is None
