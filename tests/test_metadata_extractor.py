"""Tests for metadata_extractor module."""

from fetch_guard.scripts import metadata_extractor


class TestNullMetadata:
    """Ensure the null schema is correct."""

    def test_all_keys_present(self):
        result = metadata_extractor.null_metadata()
        for key in ("title", "author", "date", "description", "canonical_url", "image"):
            assert key in result
            assert result[key] is None


class TestExtract:
    """Tests for metadata_extractor.extract()."""

    def test_empty_html(self):
        result = metadata_extractor.extract("")
        assert result["title"] is None
        assert result["author"] is None

    def test_json_ld_basic(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "headline": "Test Title", "author": {"name": "Jane Doe"},
         "datePublished": "2026-01-15", "description": "A test article",
         "url": "https://example.com/article", "image": "https://example.com/img.jpg"}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["title"] == "Test Title"
        assert result["author"] == "Jane Doe"
        assert result["date"] == "2026-01-15"
        assert result["description"] == "A test article"
        assert result["canonical_url"] == "https://example.com/article"
        assert result["image"] == "https://example.com/img.jpg"

    def test_opengraph_fallback(self):
        html = """
        <html><head>
        <meta property="og:title" content="OG Title" />
        <meta property="og:description" content="OG Desc" />
        <meta property="og:image" content="https://example.com/og.jpg" />
        <meta property="og:url" content="https://example.com/page" />
        <meta property="article:author" content="OG Author" />
        <meta property="article:published_time" content="2026-02-01" />
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["title"] == "OG Title"
        assert result["description"] == "OG Desc"
        assert result["image"] == "https://example.com/og.jpg"
        assert result["author"] == "OG Author"
        assert result["date"] == "2026-02-01"

    def test_meta_tag_fallback(self):
        html = """
        <html><head>
        <meta name="author" content="Meta Author" />
        <meta name="description" content="Meta Desc" />
        <meta name="date" content="2026-03-01" />
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["author"] == "Meta Author"
        assert result["description"] == "Meta Desc"
        assert result["date"] == "2026-03-01"

    def test_json_ld_takes_priority_over_og(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "headline": "JSON-LD Title"}
        </script>
        <meta property="og:title" content="OG Title" />
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["title"] == "JSON-LD Title"

    def test_og_takes_priority_over_meta(self):
        html = """
        <html><head>
        <meta property="og:description" content="OG Desc" />
        <meta name="description" content="Meta Desc" />
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["description"] == "OG Desc"

    def test_missing_fields_are_none(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "headline": "Only Title"}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["title"] == "Only Title"
        assert result["author"] is None
        assert result["date"] is None
        assert result["image"] is None

    def test_malformed_html_returns_partial(self):
        html = "<html><head><meta name='author' content='Bob'></head>"
        result = metadata_extractor.extract(html)
        assert result["author"] == "Bob"
        assert result["title"] is None

    def test_author_as_string(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "author": "Plain String Author"}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["author"] == "Plain String Author"

    def test_author_as_list(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "author": [{"name": "First Author"}, {"name": "Second Author"}]}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["author"] == "First Author"

    def test_image_as_object(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "image": {"url": "https://example.com/photo.jpg"}}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["image"] == "https://example.com/photo.jpg"

    def test_image_as_list(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "image": ["https://example.com/first.jpg", "https://example.com/second.jpg"]}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["image"] == "https://example.com/first.jpg"

    def test_name_field_used_for_title(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "WebSite", "name": "Site Name"}
        </script>
        </head><body></body></html>
        """
        result = metadata_extractor.extract(html)
        assert result["title"] == "Site Name"
