"""Pure MIME classification, text extraction, and output limiting for web content."""

from fabrica.features.web_content_fetching.adapters.outbound.content_processing.classification import (
    ClassifiedWebContent,
    WebContentKind,
    classify_web_content,
)
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.decoding import decode_web_content
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.extraction import (
    ExtractedWebContent,
    extract_web_content,
)
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.output_limiting import (
    LimitedWebContent,
    limit_web_content,
)
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.processor import (
    ProcessedWebContent,
    process_web_content,
)

__all__ = [
    "ClassifiedWebContent",
    "ExtractedWebContent",
    "LimitedWebContent",
    "ProcessedWebContent",
    "WebContentKind",
    "classify_web_content",
    "decode_web_content",
    "extract_web_content",
    "limit_web_content",
    "process_web_content",
]
