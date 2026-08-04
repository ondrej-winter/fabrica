"""Read-only file adapter for selected Agent Skill script metadata."""

from hashlib import sha256
from pathlib import Path

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_SKILL_SCRIPT_BYTES,
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptMetadata,
    skill_script_type_for_suffix,
)
from fabrica.features.agent_runtime.application.ports import SkillScriptMetadataLoadError

DEFAULT_SKILL_ROOT = Path.cwd() / ".agents" / "skills"
_PATH_OUTSIDE_ROOT_MESSAGE = "selected skill script path is outside the configured skill root"
_MISSING_SCRIPT_MESSAGE = "selected skill script was not found"
_AMBIGUOUS_SCRIPT_MESSAGE = "selected skill script matched more than one configured skill root"
_INVALID_SCRIPT_FILE_MESSAGE = "selected skill script path is not a readable file"
_UNSUPPORTED_SCRIPT_TYPE_MESSAGE = "selected skill script type is not supported"
_SCRIPT_TOO_LARGE_MESSAGE = "selected skill script exceeds the adapter byte-size limit"
_SCRIPT_READ_ERROR_MESSAGE = "selected skill script could not be read"

type _ErrorMetadata = dict[str, str | int]


class SkillScriptFileMetadataLoader:
    """Load metadata for explicitly selected local Agent Skill script files.

    The adapter maps application-level ``SelectedSkillScript`` identifiers to
    configured skill roots at the filesystem edge. It reads bounded file bytes to
    compute metadata only; it does not execute scripts, scan skill directories,
    follow references recursively, mutate files, or persist script contents.
    """

    def __init__(
        self,
        *,
        skill_roots: tuple[Path, ...] | None = None,
        max_script_bytes: int = DEFAULT_MAX_SKILL_SCRIPT_BYTES,
        verbose_diagnostics: bool = False,
    ) -> None:
        self._skill_roots = tuple(skill_roots or (DEFAULT_SKILL_ROOT,))
        self._max_script_bytes = max_script_bytes
        self._verbose_diagnostics = verbose_diagnostics

    def load_metadata(self, selection: SelectedSkillScript) -> SkillScriptMetadata:
        """Load read-only metadata for an explicitly selected skill script."""
        skill_relative_path = _relative_path_from_id(selection.skill_id)
        script_relative_path = _relative_path_from_id(selection.script_id)
        script_file = self._find_selected_file(selection, skill_relative_path, script_relative_path)
        suffix = script_file.suffix.lower()
        script_type = skill_script_type_for_suffix(suffix)
        if script_type is None:
            raise self._load_error(
                _UNSUPPORTED_SCRIPT_TYPE_MESSAGE,
                selection=selection,
                category="unsupported_script_type",
                path=script_file,
            )

        script_bytes = self._read_script_bytes(selection, script_file)
        byte_size = len(script_bytes)
        if byte_size > self._max_script_bytes:
            raise self._load_error(
                _SCRIPT_TOO_LARGE_MESSAGE,
                selection=selection,
                category="script_size_exceeds_adapter_limit",
                path=script_file,
                metadata={"byte_size": byte_size, "max_script_bytes": self._max_script_bytes},
            )

        binding = SkillScriptApprovalBinding(
            skill_id=selection.skill_id,
            script_id=selection.script_id,
            script_type=script_type,
            suffix=suffix,
            byte_size=byte_size,
            content_digest=f"sha256:{sha256(script_bytes).hexdigest()}",
        )
        return SkillScriptMetadata(
            selection=selection,
            binding=binding,
            metadata={"file_name": script_file.name},
        )

    def _find_selected_file(
        self,
        selection: SelectedSkillScript,
        skill_relative_path: Path,
        script_relative_path: Path,
    ) -> Path:
        matches: list[Path] = []
        for skill_root in self._skill_roots:
            root = skill_root.resolve(strict=False)
            skill_directory = (root / skill_relative_path).resolve(strict=False)
            candidate = (skill_directory / script_relative_path).resolve(strict=False)
            if not skill_directory.is_relative_to(root):
                raise self._load_error(
                    _PATH_OUTSIDE_ROOT_MESSAGE,
                    selection=selection,
                    category="invalid_script_path",
                    path=skill_directory,
                )
            if not candidate.is_relative_to(skill_directory):
                raise self._load_error(
                    _PATH_OUTSIDE_ROOT_MESSAGE,
                    selection=selection,
                    category="invalid_script_path",
                    path=candidate,
                )
            if candidate.exists():
                if not candidate.is_file():
                    raise self._load_error(
                        _INVALID_SCRIPT_FILE_MESSAGE,
                        selection=selection,
                        category="invalid_script_file",
                        path=candidate,
                    )
                matches.append(candidate)

        if len(matches) > 1:
            raise self._load_error(
                _AMBIGUOUS_SCRIPT_MESSAGE,
                selection=selection,
                category="ambiguous_script",
            )
        if matches:
            return matches[0]

        raise self._load_error(
            _MISSING_SCRIPT_MESSAGE,
            selection=selection,
            category="missing_script",
        )

    def _read_script_bytes(self, selection: SelectedSkillScript, script_file: Path) -> bytes:
        try:
            return script_file.read_bytes()
        except OSError as err:
            raise self._load_error(
                _SCRIPT_READ_ERROR_MESSAGE,
                selection=selection,
                category="script_read_error",
                path=script_file,
            ) from err

    def _load_error(
        self,
        message: str,
        *,
        selection: SelectedSkillScript,
        category: str,
        path: Path | None = None,
        metadata: _ErrorMetadata | None = None,
    ) -> SkillScriptMetadataLoadError:
        error_metadata: _ErrorMetadata = {
            "diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe",
        }
        if self._verbose_diagnostics and path is not None:
            error_metadata["path"] = str(path)
        if metadata is not None:
            error_metadata.update(metadata)
        return SkillScriptMetadataLoadError(
            message,
            skill_id=selection.skill_id,
            script_id=selection.script_id,
            category=category,
            metadata=error_metadata,
        )


def _relative_path_from_id(identifier: str) -> Path:
    relative_path = Path(identifier)
    if relative_path.is_absolute():
        msg = "selected skill script identifiers must be relative"
        raise SkillScriptMetadataLoadError(
            msg,
            skill_id=identifier,
            script_id=identifier,
            category="invalid_script_path",
            metadata={"diagnostic_mode": "safe"},
        )
    return relative_path
