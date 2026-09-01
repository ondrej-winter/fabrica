"""Canonical JSON-compatible formatting for public-web fetch outcomes."""

from fabrica.features.web_content_fetching.application.dtos import (
    FetchFailure,
    FetchRedirect,
    FetchResult,
    FetchSuccess,
    FetchWebContentResult,
)


def fetch_web_content_result_payload(result: FetchWebContentResult) -> dict[str, object]:
    """Return the stable complete payload for one fetch batch."""
    return {
        "results": [fetch_result_payload(item) for item in result.results],
        "batch_content_truncated": result.batch_content_truncated,
    }


def fetch_result_payload(result: FetchResult) -> dict[str, object]:
    """Return the stable payload for one independent fetch outcome."""
    if not isinstance(result, FetchSuccess | FetchFailure):
        msg = "result must be a fetch outcome"
        raise TypeError(msg)
    common = {
        "requested_url": result.requested_url,
        "final_url": result.final_url,
        "status": result.status,
        "redirects": [_redirect_payload(redirect) for redirect in result.redirects],
        "trust": result.trust,
    }
    if isinstance(result, FetchSuccess):
        return {
            **common,
            "success": True,
            "content_type": result.content_type,
            "media_type": result.media_type,
            "size_bytes": result.size_bytes,
            "content_format": result.content_format.value,
            "content": result.content,
            "content_chars": result.content_chars,
            "returned_chars": result.returned_chars,
            "truncated": result.truncated,
        }
    return {
        **common,
        "success": False,
        "error": {
            "code": result.error.code.value,
            "message": result.error.message,
            "metadata": dict(result.error.metadata),
        },
    }


def _redirect_payload(redirect: FetchRedirect) -> dict[str, object]:
    return {"status": redirect.status, "from_url": redirect.from_url, "to_url": redirect.to_url}


__all__ = ["fetch_result_payload", "fetch_web_content_result_payload"]
