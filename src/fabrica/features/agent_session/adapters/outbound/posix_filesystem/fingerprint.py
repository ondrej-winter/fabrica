"""Deterministic, fail-closed workspace fingerprint adapter."""

from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import Path

from fabrica.features.agent_session.application.dtos import WorkspaceFingerprint


@dataclass(frozen=True, slots=True)
class PosixWorkspaceFingerprintBuilder:
    """Hash regular workspace files after mandatory and user-selected exclusions."""

    workspace_root: Path

    def build(self) -> WorkspaceFingerprint:
        """Return a canonical snapshot or unavailable evidence on scan uncertainty."""
        try:
            root = self.workspace_root.resolve(strict=True)
            patterns = _load_patterns(root)
            entries: list[str] = []
            paths = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
            for path in paths:
                relative = path.relative_to(root).as_posix()
                if _excluded(relative, patterns):
                    continue
                if path.is_symlink():
                    return _unavailable("workspace contains a symlink")
                if path.is_dir():
                    continue
                if not path.is_file():
                    return _unavailable("workspace contains an unsupported path type")
                before = path.stat()
                digest = _digest_file(path)
                after = path.stat()
                before_identity = before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
                after_identity = after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
                if before_identity != after_identity:
                    return _unavailable("workspace changed during fingerprinting")
                entries.append(f"{relative}\0sha256:{digest}")
            manifest = tuple(entries)
            return WorkspaceFingerprint(
                digest="sha256:" + sha256("\n".join(manifest).encode()).hexdigest(), manifest=manifest
            )
        except (OSError, ValueError) as err:
            return _unavailable(str(err) or type(err).__name__)


def _load_patterns(root: Path) -> tuple[str, ...]:
    path = root / ".fabricaignore"
    if not path.exists():
        return ()
    patterns: list[str] = []
    for raw_pattern in path.read_text(encoding="utf-8").splitlines():
        pattern = raw_pattern.strip()
        if not pattern or pattern.startswith("#"):
            continue
        _validate_pattern(pattern)
        patterns.append(pattern)
    return tuple(patterns)


def _validate_pattern(pattern: str) -> None:
    candidate = pattern.removeprefix("!")
    if not candidate or "\0" in candidate or candidate.startswith("/") or "\\" in candidate:
        msg = "invalid .fabricaignore pattern"
        raise ValueError(msg)
    if ".." in candidate.split("/"):
        msg = "invalid .fabricaignore pattern"
        raise ValueError(msg)


def _excluded(relative: str, patterns: tuple[str, ...]) -> bool:
    if relative == ".fabrica" or relative.startswith(".fabrica/"):
        return True
    if relative == ".git" or relative.startswith(".git/"):
        return True
    matched = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        candidate = pattern.removeprefix("!").rstrip("/")
        if fnmatchcase(relative, candidate) or fnmatchcase(relative, candidate + "/*"):
            matched = not negated
    return matched


def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unavailable(reason: str) -> WorkspaceFingerprint:
    return WorkspaceFingerprint(digest=None, unavailable_reason=reason)
