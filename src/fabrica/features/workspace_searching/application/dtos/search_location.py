"""Backend-neutral unhydrated locations emitted by workspace search backends."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchLocation:
    """One backend match location before shared source-context hydration.

    ``column_byte_offset`` is zero-based within UTF-8 source bytes. The context
    hydrator converts it to the public one-based Unicode-character column.
    """

    path: str
    line: int
    column_byte_offset: int
    matched_text: str

    def __post_init__(self) -> None:
        if not self.path or self.path == "." or self.path.startswith("/") or ".." in self.path.split("/"):
            msg = "path must identify a non-escaping workspace file"
            raise ValueError(msg)
        if self.line < 1:
            msg = "line must be one-based"
            raise ValueError(msg)
        if self.column_byte_offset < 0:
            msg = "column_byte_offset must not be negative"
            raise ValueError(msg)
        if not self.matched_text:
            msg = "matched_text must not be empty"
            raise ValueError(msg)


__all__ = ["SearchLocation"]
