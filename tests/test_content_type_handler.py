"""Tests for content_type_handler module."""

from fetch_guard.scripts import content_type_handler

# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------

class TestClassify:
    """Tests for content type classification."""

    def test_html_content_type(self):
        assert content_type_handler.classify("text/html; charset=utf-8") == "html"

    def test_xhtml_content_type(self):
        assert content_type_handler.classify("application/xhtml+xml") == "html"

    def test_json_content_type(self):
        assert content_type_handler.classify("application/json") == "json"

    def test_json_with_charset(self):
        assert content_type_handler.classify("application/json; charset=utf-8") == "json"

    def test_text_json(self):
        assert content_type_handler.classify("text/json") == "json"

    def test_plain_text(self):
        assert content_type_handler.classify("text/plain") == "plain_text"

    def test_markdown(self):
        assert content_type_handler.classify("text/markdown") == "markdown"

    def test_x_markdown(self):
        assert content_type_handler.classify("text/x-markdown") == "markdown"

    def test_xml_application(self):
        assert content_type_handler.classify("application/xml") == "xml"

    def test_xml_text(self):
        assert content_type_handler.classify("text/xml") == "xml"

    def test_rss_xml(self):
        assert content_type_handler.classify("application/rss+xml") == "xml"

    def test_atom_xml(self):
        assert content_type_handler.classify("application/atom+xml") == "xml"

    def test_csv(self):
        assert content_type_handler.classify("text/csv") == "csv"

    def test_application_csv(self):
        assert content_type_handler.classify("application/csv") == "csv"

    def test_binary_image(self):
        assert content_type_handler.classify("image/png") == "binary"

    def test_binary_pdf(self):
        assert content_type_handler.classify("application/pdf") == "binary"

    def test_binary_octet_stream(self):
        assert content_type_handler.classify("application/octet-stream") == "binary"

    def test_binary_video(self):
        assert content_type_handler.classify("video/mp4") == "binary"

    def test_binary_audio(self):
        assert content_type_handler.classify("audio/mpeg") == "binary"

    def test_unknown_type(self):
        assert content_type_handler.classify("application/x-custom-thing") == "unknown"

    def test_empty_header(self):
        assert content_type_handler.classify("") == "unknown"

    def test_none_header(self):
        assert content_type_handler.classify(None) == "unknown"


class TestClassifySniffing:
    """Tests for text/plain HTML sniffing."""

    def test_plain_text_with_doctype_reclassifies_as_html(self):
        body = "<!DOCTYPE html><html><body>Hello</body></html>"
        assert content_type_handler.classify("text/plain", body) == "html"

    def test_plain_text_with_html_tag_reclassifies(self):
        body = "<html><head></head><body>Hello</body></html>"
        assert content_type_handler.classify("text/plain", body) == "html"

    def test_plain_text_with_html_tag_case_insensitive(self):
        body = "  <HTML><BODY>Hello</BODY></HTML>"
        assert content_type_handler.classify("text/plain", body) == "html"

    def test_plain_text_without_html_stays_plain(self):
        body = "Just some plain text content here."
        assert content_type_handler.classify("text/plain", body) == "plain_text"

    def test_sniffing_only_applies_to_plain_text(self):
        body = "<!DOCTYPE html><html><body>Hello</body></html>"
        assert content_type_handler.classify("application/json", body) == "json"


# ---------------------------------------------------------------------------
# handle()
# ---------------------------------------------------------------------------

class TestHandleJson:
    """Tests for JSON handling."""

    def test_valid_json_formatted(self):
        raw = '{"name":"test","value":42}'
        result = content_type_handler.handle("json", raw)
        assert result.startswith("```json\n")
        assert result.endswith("\n```")
        assert '"name": "test"' in result
        assert '"value": 42' in result

    def test_invalid_json_returns_raw(self):
        raw = "not valid json {{"
        result = content_type_handler.handle("json", raw)
        assert result == f"```json\n{raw}\n```"

    def test_json_array(self):
        raw = '[1, 2, 3]'
        result = content_type_handler.handle("json", raw)
        assert "[\n  1,\n  2,\n  3\n]" in result


class TestHandleXml:
    """Tests for XML/RSS/Atom handling."""

    def test_rss_feed_rendered_as_markdown(self):
        rss = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <description>A test RSS feed</description>
            <item>
              <title>First Post</title>
              <link>https://example.com/1</link>
              <description>First post content</description>
            </item>
            <item>
              <title>Second Post</title>
              <link>https://example.com/2</link>
              <description>Second post content</description>
            </item>
          </channel>
        </rss>"""
        result = content_type_handler.handle("xml", rss)
        assert "# Test Feed" in result
        assert "[First Post](https://example.com/1)" in result
        assert "[Second Post](https://example.com/2)" in result
        assert "First post content" in result

    def test_atom_feed_rendered_as_markdown(self):
        atom = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Atom Feed</title>
          <subtitle>A test Atom feed</subtitle>
          <entry>
            <title>Entry One</title>
            <link href="https://example.com/entry1"/>
            <summary>Summary of entry one</summary>
          </entry>
        </feed>"""
        result = content_type_handler.handle("xml", atom)
        assert "# Atom Feed" in result
        assert "[Entry One](https://example.com/entry1)" in result
        assert "Summary of entry one" in result

    def test_generic_xml_fenced_block(self):
        xml = """<?xml version="1.0"?><data><item>value</item></data>"""
        result = content_type_handler.handle("xml", xml)
        assert result.startswith("```xml\n")
        assert result.endswith("\n```")

    def test_malformed_xml_fenced_block(self):
        xml = "<not valid xml>>>"
        result = content_type_handler.handle("xml", xml)
        assert result.startswith("```xml\n")


class TestHandleCsv:
    """Tests for CSV handling."""

    def test_csv_to_markdown_table(self):
        raw = "name,age,city\nAlice,30,NYC\nBob,25,LA"
        result = content_type_handler.handle("csv", raw)
        assert "| name | age | city |" in result
        assert "| --- | --- | --- |" in result
        assert "| Alice | 30 | NYC |" in result
        assert "| Bob | 25 | LA |" in result

    def test_csv_single_row(self):
        raw = "col1,col2\nval1,val2"
        result = content_type_handler.handle("csv", raw)
        assert "| col1 | col2 |" in result
        assert "| val1 | val2 |" in result

    def test_csv_header_only(self):
        raw = "a,b,c"
        result = content_type_handler.handle("csv", raw)
        assert "| a | b | c |" in result
        assert "| --- | --- | --- |" in result


class TestHandlePlainText:
    """Tests for plain text and markdown handling."""

    def test_plain_text_passthrough(self):
        raw = "Hello, this is plain text."
        assert content_type_handler.handle("plain_text", raw) == raw

    def test_markdown_passthrough(self):
        raw = "# Heading\n\nSome **bold** text."
        assert content_type_handler.handle("markdown", raw) == raw

    def test_unknown_passthrough(self):
        raw = "some content"
        assert content_type_handler.handle("unknown", raw) == raw


class TestHandleBinary:
    """Tests for binary content."""

    def test_binary_returns_none(self):
        assert content_type_handler.handle("binary", b"") is None
