"""Tests for the read-only Agent Skill script metadata file adapter."""

from hashlib import sha256
from pathlib import Path

import pytest

from fabrica.features.agent_runtime.adapters.outbound.skill_script_file import SkillScriptFileMetadataLoader
from fabrica.features.agent_runtime.application.dtos import SelectedSkillScript, SkillScriptSnapshot, SkillScriptType
from fabrica.features.agent_runtime.application.ports import SkillScriptMetadataLoadError
from tests.synthetic_values import PRIVATE_FILE_CONTENT

SYNTHETIC_SECRET = PRIVATE_FILE_CONTENT


def test_load_metadata_returns_python_script_metadata_from_selected_script(tmp_path: Path) -> None:
    script_bytes = b"print('metadata only')\n"
    _write_script(tmp_path, "python-testing", "scripts/check.py", script_bytes)

    metadata = SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_metadata(
        SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py", label="Check script"),
    )

    assert metadata.selection.skill_id == "python-testing"
    assert metadata.selection.script_id == "scripts/check.py"
    assert metadata.binding.skill_id == "python-testing"
    assert metadata.binding.script_id == "scripts/check.py"
    assert metadata.binding.script_type is SkillScriptType.PYTHON
    assert metadata.binding.suffix == ".py"
    assert metadata.binding.byte_size == len(script_bytes)
    assert metadata.binding.content_digest == f"sha256:{sha256(script_bytes).hexdigest()}"
    assert metadata.metadata == {"file_name": "check.py"}


def test_load_metadata_returns_shell_script_type_for_sh_suffix(tmp_path: Path) -> None:
    _write_script(tmp_path, "shell-testing", "scripts/check.sh", b"echo metadata-only\n")

    metadata = SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_metadata(
        SelectedSkillScript(skill_id="shell-testing", script_id="scripts/check.sh"),
    )

    assert metadata.binding.script_type is SkillScriptType.SHELL
    assert metadata.binding.suffix == ".sh"


def test_load_snapshot_returns_script_bytes_and_matching_binding_from_one_read(tmp_path: Path) -> None:
    script_bytes = b"print('snapshot')\n"
    script_file = _write_script(tmp_path, "python-testing", "scripts/check.py", script_bytes)
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")

    snapshot = SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_snapshot(selection)

    assert isinstance(snapshot, SkillScriptSnapshot)
    assert snapshot.selection == selection
    assert snapshot.content == script_bytes
    assert snapshot.binding.byte_size == len(script_bytes)
    assert snapshot.binding.content_digest == f"sha256:{sha256(script_bytes).hexdigest()}"
    assert snapshot.metadata == {"file_name": script_file.name}


def test_load_snapshot_content_is_not_affected_by_later_script_replacement(tmp_path: Path) -> None:
    script_file = _write_script(tmp_path, "python-testing", "scripts/check.py", b"print('approved')\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")

    snapshot = SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_snapshot(selection)
    script_file.write_bytes(b"print('replacement')\n")

    assert snapshot.content == b"print('approved')\n"


def test_load_metadata_searches_configured_skill_roots_and_rejects_ambiguous_matches(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_script(second_root, "python-testing", "scripts/check.py", b"print('ok')\n")

    loaded = SkillScriptFileMetadataLoader(skill_roots=(first_root, second_root)).load_metadata(
        SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py"),
    )

    assert loaded.binding.byte_size == len(b"print('ok')\n")

    _write_script(first_root, "python-testing", "scripts/check.py", b"print('ambiguous')\n")
    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(first_root, second_root)).load_metadata(
            SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py"),
        )

    assert exc_info.value.category == "ambiguous_script"
    assert "path" not in exc_info.value.metadata


def test_load_metadata_raises_safe_missing_script_error_without_private_path(tmp_path: Path) -> None:
    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_metadata(
            SelectedSkillScript(skill_id="missing", script_id="scripts/check.py"),
        )

    assert exc_info.value.skill_id == "missing"
    assert exc_info.value.script_id == "scripts/check.py"
    assert exc_info.value.category == "missing_script"
    assert exc_info.value.metadata == {"diagnostic_mode": "safe"}
    assert str(tmp_path) not in str(exc_info.value)


def test_load_metadata_can_include_verbose_path_diagnostics_when_enabled(tmp_path: Path) -> None:
    _write_script(tmp_path, "unsupported", "scripts/check.rb", b"puts 'unsupported'\n")

    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(tmp_path,), verbose_diagnostics=True).load_metadata(
            SelectedSkillScript(skill_id="unsupported", script_id="scripts/check.rb"),
        )

    assert exc_info.value.category == "unsupported_script_type"
    assert exc_info.value.metadata["diagnostic_mode"] == "verbose"
    assert isinstance(exc_info.value.metadata["path"], str)
    assert exc_info.value.metadata["path"].endswith("unsupported/scripts/check.rb")


def test_load_metadata_rejects_directory_where_script_should_be(tmp_path: Path) -> None:
    script_directory = tmp_path / "directory-shape" / "scripts" / "check.py"
    script_directory.mkdir(parents=True)

    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_metadata(
            SelectedSkillScript(skill_id="directory-shape", script_id="scripts/check.py"),
        )

    assert exc_info.value.category == "invalid_script_file"


def test_load_metadata_rejects_unsupported_suffix_without_reading_script_bytes(tmp_path: Path) -> None:
    script_file = _write_script(tmp_path, "unsupported", "scripts/check.rb", b"puts 'unsupported'\n")

    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_metadata(
            SelectedSkillScript(skill_id="unsupported", script_id="scripts/check.rb"),
        )

    assert script_file.read_bytes() == b"puts 'unsupported'\n"
    assert exc_info.value.category == "unsupported_script_type"


def test_load_metadata_rejects_path_traversal_without_exposing_file_contents(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    skill_root = tmp_path / "skills"
    _write_script(private_root, "escaped", "secret.py", SYNTHETIC_SECRET.encode())
    linked_private_root = skill_root / "linked-private"
    linked_private_root.parent.mkdir(parents=True)
    linked_private_root.symlink_to(private_root, target_is_directory=True)

    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(skill_root,)).load_metadata(
            SelectedSkillScript(skill_id="linked-private/escaped", script_id="secret.py"),
        )

    assert exc_info.value.category == "invalid_script_path"
    assert SYNTHETIC_SECRET not in str(exc_info.value)
    assert SYNTHETIC_SECRET not in str(exc_info.value.metadata)


def test_load_metadata_rejects_oversized_script_without_returning_digest(tmp_path: Path) -> None:
    _write_script(tmp_path, "too-large", "scripts/check.py", b"x" * 5)

    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        SkillScriptFileMetadataLoader(skill_roots=(tmp_path,), max_script_bytes=4).load_metadata(
            SelectedSkillScript(skill_id="too-large", script_id="scripts/check.py"),
        )

    assert exc_info.value.category == "script_size_exceeds_adapter_limit"
    assert exc_info.value.metadata == {
        "diagnostic_mode": "safe",
        "byte_size": 5,
        "max_script_bytes": 4,
    }
    assert "sha256" not in str(exc_info.value.metadata)


def test_constructing_loader_does_not_read_skill_roots(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-root"

    loader = SkillScriptFileMetadataLoader(skill_roots=(missing_root,))

    assert loader is not None
    assert not missing_root.exists()


def test_load_metadata_treats_executable_looking_script_as_inert_bytes(tmp_path: Path) -> None:
    script_bytes = b"#!/bin/sh\necho should-not-run > created.txt\n"
    _write_script(tmp_path, "shell-testing", "scripts/run.sh", script_bytes)

    metadata = SkillScriptFileMetadataLoader(skill_roots=(tmp_path,)).load_metadata(
        SelectedSkillScript(skill_id="shell-testing", script_id="scripts/run.sh"),
    )

    assert metadata.binding.content_digest == f"sha256:{sha256(script_bytes).hexdigest()}"
    assert not (tmp_path / "shell-testing" / "scripts" / "created.txt").exists()


def _write_script(root: Path, skill_id: str, script_id: str, script_bytes: bytes) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_bytes(script_bytes)
    return script_file
