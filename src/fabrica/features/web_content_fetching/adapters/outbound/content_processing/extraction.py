"""Extract normalized textual representations from decoded web responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment
from markdownify import markdownify

from fabrica.features.web_content_fetching.adapters.outbound.content_processing.classification import WebContentKind
from fabrica.features.web_content_fetching.application.dtos import FetchContentFormat, FetchError, FetchErrorCode


@dataclass(frozen=True, slots=True)
class ExtractedWebContent:
    """Normalized content plus optional non-fatal parse diagnostics."""

    content: str
    content_format: FetchContentFormat
    parse_warning: str | None = None


def extract_web_content(text: str, *, kind: WebContentKind, final_url: str) -> ExtractedWebContent | FetchError:
    """Convert decoded text to the output format for its classified media family."""
    if kind is WebContentKind.HTML:
        return _extract_html(text, final_url=final_url)
    if kind is WebContentKind.JSON:
        return _extract_json(text)
    if kind is WebContentKind.XML:
        return ExtractedWebContent(content=_normalize_text(text), content_format=FetchContentFormat.XML)
    if kind is WebContentKind.MARKDOWN:
        return ExtractedWebContent(content=_normalize_text(text), content_format=FetchContentFormat.MARKDOWN)
    return ExtractedWebContent(content=_normalize_text(text), content_format=FetchContentFormat.TEXT)


def _extract_html(text: str, *, final_url: str) -> ExtractedWebContent | FetchError:
    """Remove unsafe/noisy HTML nodes and convert parsed markup to Markdown."""
    try:
        soup = BeautifulSoup(text, "html.parser")
        for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
            comment.extract()
        for element in soup(("script", "style", "noscript")):
            element.decompose()
        for link in soup.find_all("a", href=True):
            link["href"] = urljoin(final_url, str(link["href"]))
        return ExtractedWebContent(
            content=_normalize_text(markdownify(str(soup), heading_style="ATX")),
            content_format=FetchContentFormat.MARKDOWN,
        )
    except AttributeError, TypeError, ValueError:
        return FetchError(
            code=FetchErrorCode.CONTENT_EXTRACTION_FAILED,
            message="The HTML response could not be converted to readable content",
        )


def _extract_json(text: str) -> ExtractedWebContent:
    """Pretty-print valid JSON while retaining invalid textual JSON for debugging."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return ExtractedWebContent(
            content=_normalize_text(text),
            content_format=FetchContentFormat.TEXT,
            parse_warning=FetchErrorCode.INVALID_JSON.value,
        )
    return ExtractedWebContent(
        content=json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True),
        content_format=FetchContentFormat.JSON,
    )


def _normalize_text(text: str) -> str:
    """Normalize line endings and outer whitespace without deleting meaningful body text."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


__all__ = ["ExtractedWebContent", "extract_web_content"]
