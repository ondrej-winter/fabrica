"""Aggregate content allocation for completed public-web fetch results."""

from dataclasses import replace

from fabrica.features.web_content_fetching.application.dtos import FetchResult, FetchSuccess, FetchWebContentResult


def limit_batch_content(results: tuple[FetchResult, ...], *, max_content_chars: int) -> FetchWebContentResult:
    """Retain every outcome while allocating the aggregate content budget in input order."""
    if not isinstance(max_content_chars, int) or isinstance(max_content_chars, bool) or max_content_chars < 1:
        msg = "max_content_chars must be a positive integer"
        raise ValueError(msg)

    remaining = max_content_chars
    limited: list[FetchResult] = []
    batch_content_truncated = False
    for result in results:
        if not isinstance(result, FetchSuccess):
            limited.append(result)
            continue
        content = result.content[:remaining]
        truncated = result.truncated or len(content) < len(result.content)
        batch_content_truncated = batch_content_truncated or len(content) < len(result.content)
        limited.append(
            replace(
                result,
                content=content,
                content_chars=len(content),
                returned_chars=len(content),
                truncated=truncated,
            )
        )
        remaining -= len(content)
    return FetchWebContentResult(tuple(limited), batch_content_truncated=batch_content_truncated)


__all__ = ["limit_batch_content"]
