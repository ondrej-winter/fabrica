"""Read-only file adapter for selected Agent Skill markdown context."""

from pathlib import Path
from typing import TypedDict

import yaml
from yaml import YAMLError

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillResourceContext,
    SelectedSkill,
    SelectedSkillResource,
    SkillDefinition,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError, SkillDefinitionLoadError

SKILL_FILE_NAME = "SKILL.md"
DEFAULT_SKILL_ROOT = Path.cwd() / ".agents" / "skills"
ALLOWED_RESOURCE_SUFFIX_MEDIA_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".toml": "application/toml",
    ".txt": "text/plain",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}
_PATH_OUTSIDE_ROOT_MESSAGE = "selected skill path is outside the configured skill root"
_INVALID_SKILL_FILE_MESSAGE = "selected skill path is not a readable SKILL.md file"
_MISSING_SKILL_MESSAGE = "selected skill was not found"
_MISSING_RESOURCE_MESSAGE = "selected skill resource was not found"
_INVALID_RESOURCE_FILE_MESSAGE = "selected skill resource is not a readable text file"
_UNSUPPORTED_RESOURCE_TYPE_MESSAGE = "selected skill resource type is not allowed"
_INVALID_UTF8_MESSAGE = "selected skill markdown is not valid UTF-8"
_INVALID_RESOURCE_UTF8_MESSAGE = "selected skill resource is not valid UTF-8"
_READ_ERROR_MESSAGE = "selected skill markdown could not be read"
_RESOURCE_READ_ERROR_MESSAGE = "selected skill resource could not be read"
_EMPTY_MARKDOWN_MESSAGE = "selected skill markdown is empty"
_EMPTY_RESOURCE_MESSAGE = "selected skill resource text is empty"
_UTF8_BOM_MESSAGE = "selected skill markdown must not contain a UTF-8 BOM"
_MISSING_FRONTMATTER_MESSAGE = "selected skill markdown must start with YAML frontmatter"
_UNCLOSED_FRONTMATTER_MESSAGE = "selected skill markdown has unclosed YAML frontmatter"
_INVALID_FRONTMATTER_MESSAGE = "selected skill markdown has invalid YAML frontmatter"
_INVALID_FRONTMATTER_FIELDS_MESSAGE = "selected skill markdown has invalid frontmatter fields"
_MISSING_FRONTMATTER_FIELDS_MESSAGE = "selected skill markdown requires string name and description fields"
_INVALID_DISABLED_FIELD_MESSAGE = "selected skill markdown disabled field must be a boolean"
_DIRECTORY_NAME_MISMATCH_MESSAGE = "selected skill directory must match the frontmatter name"


class _SkillFrontmatter(TypedDict):
    """Validated YAML frontmatter fields for one skill definition."""

    name: str
    description: str
    disabled: bool
    metadata: dict[str, object]


class SkillMarkdownFileDefinitionLoader:
    """Load canonical YAML-frontmatter definitions from selected ``SKILL.md`` files."""

    def __init__(
        self,
        *,
        skill_roots: tuple[Path, ...] | None = None,
        verbose_diagnostics: bool = False,
    ) -> None:
        self._skill_roots = (DEFAULT_SKILL_ROOT,) if skill_roots is None else tuple(skill_roots)
        self._verbose_diagnostics = verbose_diagnostics

    def load(self, selection: SelectedSkill) -> SkillDefinition:
        """Read, validate, and return one canonical skill definition."""
        skill_file = self._find_selected_file(selection)
        source_bytes = self._read_bytes(selection, skill_file)
        if source_bytes.startswith(b"\xef\xbb\xbf"):
            raise self._load_error(
                _UTF8_BOM_MESSAGE,
                selection=selection,
                category="utf8_bom",
                path=skill_file,
            )
        try:
            source = source_bytes.decode("utf-8")
        except UnicodeDecodeError as err:
            raise self._load_error(
                _INVALID_UTF8_MESSAGE,
                selection=selection,
                category="decode_error",
                path=skill_file,
            ) from err

        frontmatter, instructions = self._parse_frontmatter(selection, skill_file, source)
        self._validate_directory_name(selection, skill_file, frontmatter["name"])
        try:
            return SkillDefinition.from_skill_file_bytes(
                name=frontmatter["name"],
                description=frontmatter["description"],
                disabled=frontmatter["disabled"],
                metadata=frontmatter["metadata"],
                instructions=instructions,
                skill_file_bytes=source_bytes,
            )
        except (ValueError, TypeError) as err:
            category = "skill_too_large" if "exceed" in str(err) else "invalid_definition"
            raise self._load_error(str(err), selection=selection, category=category, path=skill_file) from err

    def _find_selected_file(self, selection: SelectedSkill) -> Path:
        skill_relative_path = _skill_relative_path(selection)
        for skill_root in self._skill_roots:
            root = skill_root.resolve(strict=False)
            candidate = (root / skill_relative_path / SKILL_FILE_NAME).resolve(strict=False)
            if not candidate.is_relative_to(root):
                raise self._load_error(
                    _PATH_OUTSIDE_ROOT_MESSAGE,
                    selection=selection,
                    category="invalid_skill_path",
                    path=candidate,
                )
            if candidate.exists():
                if not candidate.is_file():
                    raise self._load_error(
                        _INVALID_SKILL_FILE_MESSAGE,
                        selection=selection,
                        category="invalid_skill_file",
                        path=candidate,
                    )
                return candidate
        raise self._load_error(_MISSING_SKILL_MESSAGE, selection=selection, category="missing_skill")

    def _read_bytes(self, selection: SelectedSkill, skill_file: Path) -> bytes:
        try:
            return skill_file.read_bytes()
        except OSError as err:
            raise self._load_error(
                _READ_ERROR_MESSAGE,
                selection=selection,
                category="invalid_skill_file",
                path=skill_file,
            ) from err

    def _parse_frontmatter(
        self, selection: SelectedSkill, skill_file: Path, source: str
    ) -> tuple[_SkillFrontmatter, str]:
        if not source.startswith("---\n") and not source.startswith("---\r\n"):
            raise self._load_error(
                _MISSING_FRONTMATTER_MESSAGE,
                selection=selection,
                category="invalid_frontmatter",
                path=skill_file,
            )
        lines = source.splitlines(keepends=True)
        closing_index = next(
            (index for index, line in enumerate(lines[1:], start=1) if line.rstrip("\r\n") == "---"), None
        )
        if closing_index is None:
            raise self._load_error(
                _UNCLOSED_FRONTMATTER_MESSAGE,
                selection=selection,
                category="invalid_frontmatter",
                path=skill_file,
            )
        try:
            frontmatter = yaml.safe_load("".join(lines[1:closing_index]))
        except YAMLError as err:
            raise self._load_error(
                _INVALID_FRONTMATTER_MESSAGE,
                selection=selection,
                category="invalid_frontmatter",
                path=skill_file,
            ) from err
        if not isinstance(frontmatter, dict) or set(frontmatter) - {"name", "description", "disabled", "metadata"}:
            raise self._load_error(
                _INVALID_FRONTMATTER_FIELDS_MESSAGE,
                selection=selection,
                category="invalid_definition",
                path=skill_file,
            )
        if not isinstance(frontmatter.get("name"), str) or not isinstance(frontmatter.get("description"), str):
            raise self._load_error(
                _MISSING_FRONTMATTER_FIELDS_MESSAGE,
                selection=selection,
                category="invalid_definition",
                path=skill_file,
            )
        if "metadata" in frontmatter and not isinstance(frontmatter["metadata"], dict):
            raise self._load_error(
                _INVALID_FRONTMATTER_FIELDS_MESSAGE,
                selection=selection,
                category="invalid_definition",
                path=skill_file,
            )
        if "disabled" in frontmatter and not isinstance(frontmatter["disabled"], bool):
            raise self._load_error(
                _INVALID_DISABLED_FIELD_MESSAGE,
                selection=selection,
                category="invalid_definition",
                path=skill_file,
            )
        return (
            {
                "name": frontmatter["name"],
                "description": frontmatter["description"],
                "disabled": frontmatter.get("disabled", False),
                "metadata": frontmatter.get("metadata", {}),
            },
            "".join(lines[closing_index + 1 :]).lstrip("\r\n"),
        )

    def _validate_directory_name(self, selection: SelectedSkill, skill_file: Path, name: object) -> None:
        if not isinstance(name, str) or skill_file.parent.name != name:
            raise self._load_error(
                _DIRECTORY_NAME_MISMATCH_MESSAGE,
                selection=selection,
                category="invalid_definition",
                path=skill_file,
            )

    def _load_error(
        self,
        message: str,
        *,
        selection: SelectedSkill,
        category: str,
        path: Path | None = None,
    ) -> SkillDefinitionLoadError:
        metadata = {"diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe"}
        if self._verbose_diagnostics and path is not None:
            metadata["path"] = str(path)
        return SkillDefinitionLoadError(
            message,
            skill_id=selection.skill_id,
            category=category,
            metadata=metadata,
        )


class SkillResourceFileContextLoader:
    """Load explicitly selected text resources from local Agent Skill directories."""

    def __init__(
        self,
        *,
        skill_roots: tuple[Path, ...] | None = None,
        verbose_diagnostics: bool = False,
    ) -> None:
        self._skill_roots = (DEFAULT_SKILL_ROOT,) if skill_roots is None else tuple(skill_roots)
        self._verbose_diagnostics = verbose_diagnostics

    def load(self, selection: SelectedSkillResource) -> LoadedSkillResourceContext:
        """Load selected skill resource text from a configured local skill root."""
        skill_relative_path = _skill_relative_path_from_id(selection.skill_id)
        resource_relative_path = _resource_relative_path(selection)
        selected_file = self._find_selected_file(selection, skill_relative_path, resource_relative_path)
        media_type = _media_type_for_resource(selected_file)
        text = self._read_text(selection, selected_file)
        return LoadedSkillResourceContext(
            skill_id=selection.skill_id,
            resource_id=selection.resource_id,
            label=selection.label,
            text=text,
            media_type=media_type,
            metadata={"file_name": selected_file.name},
        )

    def _find_selected_file(
        self,
        selection: SelectedSkillResource,
        skill_relative_path: Path,
        resource_relative_path: Path,
    ) -> Path:
        if resource_relative_path.name == SKILL_FILE_NAME:
            raise self._load_error(
                _UNSUPPORTED_RESOURCE_TYPE_MESSAGE,
                selection=selection,
                category="unsupported_resource_type",
            )
        for skill_root in self._skill_roots:
            root = skill_root.resolve(strict=False)
            skill_directory = (root / skill_relative_path).resolve(strict=False)
            candidate = (skill_directory / resource_relative_path).resolve(strict=False)
            if not skill_directory.is_relative_to(root):
                raise self._load_error(
                    _PATH_OUTSIDE_ROOT_MESSAGE,
                    selection=selection,
                    category="invalid_resource_path",
                    path=skill_directory,
                )
            if not candidate.is_relative_to(skill_directory):
                raise self._load_error(
                    _PATH_OUTSIDE_ROOT_MESSAGE,
                    selection=selection,
                    category="invalid_resource_path",
                    path=candidate,
                )
            if candidate.exists():
                if not candidate.is_file():
                    raise self._load_error(
                        _INVALID_RESOURCE_FILE_MESSAGE,
                        selection=selection,
                        category="invalid_resource_file",
                        path=candidate,
                    )
                if candidate.suffix.lower() not in ALLOWED_RESOURCE_SUFFIX_MEDIA_TYPES:
                    raise self._load_error(
                        _UNSUPPORTED_RESOURCE_TYPE_MESSAGE,
                        selection=selection,
                        category="unsupported_resource_type",
                        path=candidate,
                    )
                return candidate

        raise self._load_error(
            _MISSING_RESOURCE_MESSAGE,
            selection=selection,
            category="missing_resource",
        )

    def _read_text(self, selection: SelectedSkillResource, resource_file: Path) -> str:
        try:
            text = resource_file.read_bytes().decode("utf-8")
        except UnicodeDecodeError as err:
            raise self._load_error(
                _INVALID_RESOURCE_UTF8_MESSAGE,
                selection=selection,
                category="decode_error",
                path=resource_file,
            ) from err
        except OSError as err:
            raise self._load_error(
                _RESOURCE_READ_ERROR_MESSAGE,
                selection=selection,
                category="invalid_resource_file",
                path=resource_file,
            ) from err

        if not text.strip():
            raise self._load_error(
                _EMPTY_RESOURCE_MESSAGE,
                selection=selection,
                category="invalid_resource_text",
                path=resource_file,
            )
        return text

    def _load_error(
        self,
        message: str,
        *,
        selection: SelectedSkillResource,
        category: str,
        path: Path | None = None,
    ) -> SkillContextLoadError:
        metadata = {
            "diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe",
            "resource_id": selection.resource_id,
        }
        if self._verbose_diagnostics and path is not None:
            metadata["path"] = str(path)
        return SkillContextLoadError(
            message,
            skill_id=selection.skill_id,
            category=category,
            metadata=metadata,
        )


def _skill_relative_path(selection: SelectedSkill) -> Path:
    return _skill_relative_path_from_id(selection.skill_id)


def _skill_relative_path_from_id(skill_id: str) -> Path:
    skill_path = Path(skill_id)
    if skill_path.is_absolute():
        msg = "selected skill path must be relative"
        raise SkillContextLoadError(
            msg,
            skill_id=skill_id,
            category="invalid_skill_path",
            metadata={"diagnostic_mode": "safe"},
        )
    return skill_path


def _resource_relative_path(selection: SelectedSkillResource) -> Path:
    resource_path = Path(selection.resource_id)
    if resource_path.is_absolute():
        msg = "selected resource path must be relative"
        raise SkillContextLoadError(
            msg,
            skill_id=selection.skill_id,
            category="invalid_resource_path",
            metadata={"diagnostic_mode": "safe", "resource_id": selection.resource_id},
        )
    return resource_path


def _media_type_for_resource(resource_file: Path) -> str:
    return ALLOWED_RESOURCE_SUFFIX_MEDIA_TYPES[resource_file.suffix.lower()]
