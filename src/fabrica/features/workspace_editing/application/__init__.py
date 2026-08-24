"""Application layer for workspace editing use cases."""

from fabrica.features.workspace_editing.application.text_snapshot import (
    PatchLineEnding,
    PatchTextDecodingError,
    PatchTextEncoding,
    PatchTextSnapshot,
    decode_patch_text,
    render_added_text,
)

__all__ = [
    "PatchLineEnding",
    "PatchTextDecodingError",
    "PatchTextEncoding",
    "PatchTextSnapshot",
    "decode_patch_text",
    "render_added_text",
]
