"""Tests for descriptor-rooted native POSIX patch operations."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.native_operations import (
    create_directory,
    native_no_replace_backend_available,
    prove_native_no_replace,
    rename_no_replace,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    sys.platform not in {"darwin", "linux"},
    reason="native no-replace backend targets macOS/Linux",
)


def test_native_no_replace_backend_proves_its_workspace_contract(tmp_path: Path) -> None:
    assert native_no_replace_backend_available() is True

    prove_native_no_replace(tmp_path)


def test_native_no_replace_rename_preserves_destination_created_after_planning(tmp_path: Path) -> None:
    (tmp_path / "parent").mkdir()
    source = tmp_path / "source"
    destination = tmp_path / "parent" / "destination"
    source.write_text("planned", encoding="utf-8")
    destination.write_text("external", encoding="utf-8")

    with pytest.raises(FileExistsError):
        rename_no_replace(tmp_path, "source", "parent/destination")

    assert source.read_text(encoding="utf-8") == "planned"
    assert destination.read_text(encoding="utf-8") == "external"


def test_descriptor_rooted_create_rejects_a_substituted_symlink_parent(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / "parent").symlink_to(external, target_is_directory=True)

    with pytest.raises(NotADirectoryError):
        create_directory(tmp_path, "parent/created", mode=0o700)

    assert not (external / "created").exists()
