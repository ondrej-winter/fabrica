"""Tests for safe extraction and normalization of textual web content."""

from fabrica.features.web_content_fetching.adapters.outbound.content_processing import (
    WebContentKind,
    extract_web_content,
)
from fabrica.features.web_content_fetching.application.dtos import FetchContentFormat, FetchError, FetchErrorCode


def test_extract_web_content_converts_parsed_html_and_removes_non_content_nodes() -> None:
    result = extract_web_content(
        """<!-- hidden --><html><head><title>Guide</title><style>bad</style></head>
        <body><h1>Heading</h1><p>Read <a href="/docs">docs</a>.</p>
        <pre><code>print('ok')</code></pre><script>alert(1)</script></body></html>""",
        kind=WebContentKind.HTML,
        final_url="https://example.com/guide",
    )

    assert not isinstance(result, FetchError)
    assert result.content_format is FetchContentFormat.MARKDOWN
    assert "# Heading" in result.content
    assert "[docs](https://example.com/docs)" in result.content
    assert "print('ok')" in result.content
    assert "alert" not in result.content
    assert "bad" not in result.content


def test_extract_web_content_preserves_tables_and_recovers_malformed_html() -> None:
    result = extract_web_content(
        "<h1>API</h1><table><tr><th>Name<th>Value<tr><td>limit<td>8</table><p>Tail",
        kind=WebContentKind.HTML,
        final_url="https://example.com/api",
    )

    assert not isinstance(result, FetchError)
    assert "# API" in result.content
    assert "Name" in result.content
    assert "limit" in result.content
    assert "Tail" in result.content


def test_extract_web_content_pretty_prints_valid_json_with_stable_key_order() -> None:
    result = extract_web_content('{"z": [1], "a": true}', kind=WebContentKind.JSON, final_url="https://example.com")

    assert not isinstance(result, FetchError)
    assert result.content_format is FetchContentFormat.JSON
    assert result.content == '{\n  "a": true,\n  "z": [\n    1\n  ]\n}'
    assert result.parse_warning is None


def test_extract_web_content_preserves_invalid_json_as_text_with_a_warning() -> None:
    result = extract_web_content("{not valid", kind=WebContentKind.JSON, final_url="https://example.com")

    assert not isinstance(result, FetchError)
    assert result.content_format is FetchContentFormat.TEXT
    assert result.content == "{not valid"
    assert result.parse_warning == FetchErrorCode.INVALID_JSON.value


def test_extract_web_content_normalizes_xml_markdown_and_plain_text() -> None:
    xml = extract_web_content("\r\n<root>value</root>\r\n", kind=WebContentKind.XML, final_url="https://example.com")
    markdown = extract_web_content("\r\n# Heading\r\n", kind=WebContentKind.MARKDOWN, final_url="https://example.com")
    text = extract_web_content("\r\nPlain text\r\n", kind=WebContentKind.TEXT, final_url="https://example.com")

    assert not isinstance(xml, FetchError)
    assert not isinstance(markdown, FetchError)
    assert not isinstance(text, FetchError)
    assert (xml.content_format, xml.content) == (FetchContentFormat.XML, "<root>value</root>")
    assert (markdown.content_format, markdown.content) == (FetchContentFormat.MARKDOWN, "# Heading")
    assert (text.content_format, text.content) == (FetchContentFormat.TEXT, "Plain text")
