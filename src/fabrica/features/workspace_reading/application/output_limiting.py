"""Pure output-bound calculations for workspace text reads."""

from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits


def fits_output_limit(content: str, candidate: str, *, max_output_chars: int) -> bool:
    """Return whether appending one rendered line remains within the output bound."""
    separator_chars = 1 if content else 0
    return len(content) + separator_chars + len(candidate) <= max_output_chars


def truncate_line_content(content: str, *, limits: ReadFilesLimits) -> tuple[str, bool]:
    """Return visibly bounded line content and whether its source was truncated."""
    if len(content) <= limits.max_line_chars:
        return content, False
    return f"{content[: limits.max_line_chars]} … [line truncated]", True


__all__ = ["fits_output_limit", "truncate_line_content"]
