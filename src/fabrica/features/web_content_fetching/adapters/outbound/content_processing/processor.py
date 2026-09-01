"""Compose pure content-processing steps for a completed web fetch response."""

from __future__ import annotations

from dataclasses import dataclass

from fabrica.features.web_content_fetching.adapters.outbound.content_processing.classification import (
    classify_web_content,
)
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.decoding import decode_web_content
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.extraction import extract_web_content
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.output_limiting import limit_web_content
from fabrica.features.web_content_fetching.application.dtos import FetchError, ProcessedWebContent


def process_web_content(
    body: bytes,
    *,
    content_type: str,
    final_url: str,
    max_chars: int,
) -> ProcessedWebContent | FetchError:
    """Classify, decode, extract, and limit one fully downloaded response body."""
    classified = classify_web_content(content_type, body)
    if isinstance(classified, FetchError):
        return classified
    decoded = decode_web_content(body, declared_charset=classified.charset)
    if isinstance(decoded, FetchError):
        return decoded
    extracted = extract_web_content(decoded, kind=classified.kind, final_url=final_url)
    if isinstance(extracted, FetchError):
        return extracted
    limited = limit_web_content(extracted.content, max_chars=max_chars)
    return ProcessedWebContent(
        media_type=classified.media_type,
        content_format=extracted.content_format,
        content=limited.content,
        content_chars=limited.content_chars,
        returned_chars=limited.returned_chars,
        truncated=limited.truncated,
        parse_warning=extracted.parse_warning,
    )


@dataclass(frozen=True, slots=True)
class WebContentProcessingAdapter:
    """Adapt the pure content-processing function to the application port."""

    def process(
        self,
        body: bytes,
        *,
        content_type: str,
        final_url: str,
        max_chars: int,
    ) -> ProcessedWebContent | FetchError:
        """Normalize one downloaded response through the pure processing pipeline."""
        return process_web_content(
            body,
            content_type=content_type,
            final_url=final_url,
            max_chars=max_chars,
        )


__all__ = ["ProcessedWebContent", "WebContentProcessingAdapter", "process_web_content"]
