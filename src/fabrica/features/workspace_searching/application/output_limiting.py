"""Pure output-bound calculations for workspace search results."""

import json

from fabrica.features.workspace_searching.application.dtos import SearchLimits


def fits_serialized_output_limit(current: str, candidate: object, *, max_output_chars: int) -> bool:
    """Return whether appending one complete serialized object stays within the bound."""
    candidate_json = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    separator_chars = 1 if current else 0
    return len(current) + separator_chars + len(candidate_json) <= max_output_chars


def truncate_line_content(content: str, *, limits: SearchLimits) -> tuple[str, bool]:
    """Return visibly bounded line content and whether its source was truncated."""
    if len(content) <= limits.max_line_chars:
        return content, False
    return f"{content[: limits.max_line_chars]} … [line truncated]", True


__all__ = ["fits_serialized_output_limit", "truncate_line_content"]
