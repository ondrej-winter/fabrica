"""Filesystem discovery adapters for configured global and workspace Agent Skills."""

from pathlib import Path

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import SkillMarkdownFileDefinitionLoader
from fabrica.features.agent_runtime.application.dtos import SelectedSkill, SkillDefinition, SkillSource
from fabrica.features.agent_runtime.application.ports import SkillDefinitionLoadError


class _SkillDirectoryProvider:
    """Discover valid direct-child skill directories from one configured root."""

    def __init__(self, *, root: Path, source: SkillSource) -> None:
        self._root = root
        self._source = source
        self._loader = SkillMarkdownFileDefinitionLoader(skill_roots=(root,))

    @property
    def source(self) -> SkillSource:
        """Return this provider's fixed Version 1 source."""
        return self._source

    def discover(self) -> tuple[SkillDefinition, ...]:
        """Discover valid direct-child skills, omitting invalid or unavailable entries."""
        try:
            directories = tuple(
                sorted((path for path in self._root.iterdir() if path.is_dir()), key=lambda path: path.name)
            )
        except OSError:
            return ()

        definitions: list[SkillDefinition] = []
        for directory in directories:
            try:
                definitions.append(self._loader.load(SelectedSkill(skill_id=directory.name)))
            except SkillDefinitionLoadError, ValueError:
                continue
        return tuple(definitions)


class GlobalSkillDirectoryProvider(_SkillDirectoryProvider):
    """Discover configured global skills from one filesystem root."""

    def __init__(self, *, root: Path) -> None:
        super().__init__(root=root, source=SkillSource.GLOBAL)


class WorkspaceSkillDirectoryProvider(_SkillDirectoryProvider):
    """Discover configured workspace skills from one filesystem root."""

    def __init__(self, *, root: Path) -> None:
        super().__init__(root=root, source=SkillSource.WORKSPACE)
