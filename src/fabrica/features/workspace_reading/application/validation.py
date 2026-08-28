"""Pure validation and normalization for workspace text ranges."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextLineRange:
    """Normalized inclusive one-based bounds for one text read."""

    start_line: int
    end_line: int | None

    def __post_init__(self) -> None:
        _validate_line_number(self.start_line, field_name="start_line")
        if self.end_line is not None:
            _validate_line_number(self.end_line, field_name="end_line")
            if self.start_line > self.end_line:
                msg = "start_line must be less than or equal to end_line"
                raise ValueError(msg)


def normalize_text_line_range(start_line: int | None, end_line: int | None) -> TextLineRange:
    """Normalize optional request bounds into inclusive one-based text bounds."""
    normalized_start = 1 if start_line is None else start_line
    return TextLineRange(start_line=normalized_start, end_line=end_line)


def _validate_line_number(value: int, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        msg = f"{field_name} must be a one-based integer"
        raise ValueError(msg)


__all__ = ["TextLineRange", "normalize_text_line_range"]
