"""Application DTOs for Agent Skill script policy evaluation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.runtime import SafeRuntimeMetadataValue
from fabrica.features.agent_runtime.application.dtos.skills import (
    DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS,
    DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS,
    SAFE_SKILL_LABEL_CHARS,
)

DEFAULT_SKILL_SCRIPT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_SKILL_SCRIPT_BYTES = 64_000
DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS = 8_000
DEFAULT_MAX_SKILL_SCRIPT_ENVIRONMENT_NAMES = 0
DEFAULT_MAX_SKILL_SCRIPT_OBSERVATION_MESSAGE_CHARS = 240
DEFAULT_MAX_SKILL_SCRIPT_DIGEST_CHARS = 128

SAFE_ENVIRONMENT_NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
SUPPORTED_SKILL_SCRIPT_SUFFIXES = frozenset((".py", ".sh"))


class SkillScriptType(StrEnum):
    """Supported selected Agent Skill script types for policy evaluation."""

    PYTHON = "python"
    SHELL = "shell"


class SkillScriptApprovalStatus(StrEnum):
    """Normalized approval lookup states for one selected script."""

    APPROVED = "approved"
    DENIED = "denied"
    NOT_REQUESTED = "not_requested"
    EXPIRED = "expired"


class SkillScriptPolicyStatus(StrEnum):
    """Normalized outcomes for selected script policy evaluation."""

    APPROVED = "approved"
    DENIED = "denied"
    UNSUPPORTED = "unsupported"
    POLICY_VIOLATION = "policy_violation"
    METADATA_ERROR = "metadata_error"


class SkillScriptExecutionStatus(StrEnum):
    """Normalized outcomes for selected script execution."""

    SUCCESS = "success"
    POLICY_DENIED = "policy_denied"
    EXECUTION_FAILED = "execution_failed"
    TIMED_OUT = "timed_out"
    UNSUPPORTED = "unsupported"
    ADAPTER_ERROR = "adapter_error"


@dataclass(frozen=True, slots=True)
class SelectedSkillScript:
    """Path-free reference to one explicitly selected Agent Skill script."""

    skill_id: str
    script_id: str
    label: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_safe_skill_text(self.skill_id, field_name="skill_id")
        _validate_safe_script_text(self.script_id, field_name="script_id")
        if self.label is not None:
            _validate_safe_script_text(self.label, field_name="label")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def display_label(self) -> str:
        """Return the safe human-facing label for this selected script."""
        return self.label or f"{self.skill_id}/{self.script_id}"


@dataclass(frozen=True, slots=True)
class SkillScriptApprovalBinding:
    """Metadata-bound identity that prevents approval reuse across script changes."""

    skill_id: str
    script_id: str
    script_type: SkillScriptType
    suffix: str
    byte_size: int
    content_digest: str

    def __post_init__(self) -> None:
        _validate_safe_skill_text(self.skill_id, field_name="skill_id")
        _validate_safe_script_text(self.script_id, field_name="script_id")
        _validate_supported_suffix(self.suffix)
        _validate_positive_int(self.byte_size, field_name="byte_size")
        _validate_content_digest(self.content_digest)


@dataclass(frozen=True, slots=True)
class SkillScriptMetadata:
    """Read-only metadata for one explicitly selected Agent Skill script."""

    selection: SelectedSkillScript
    binding: SkillScriptApprovalBinding
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.selection.skill_id != self.binding.skill_id or self.selection.script_id != self.binding.script_id:
            msg = "script metadata binding must match the selected script"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SkillScriptSnapshot:
    """Immutable script bytes bound to the metadata used for approval."""

    selection: SelectedSkillScript
    binding: SkillScriptApprovalBinding
    content: bytes
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.selection.skill_id != self.binding.skill_id or self.selection.script_id != self.binding.script_id:
            msg = "script snapshot binding must match the selected script"
            raise ValueError(msg)
        content = bytes(self.content)
        if len(content) != self.binding.byte_size:
            msg = "script snapshot content length must match its approval binding"
            raise ValueError(msg)
        if f"sha256:{sha256(content).hexdigest()}" != self.binding.content_digest:
            msg = "script snapshot content digest must match its approval binding"
            raise ValueError(msg)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SkillScriptApprovalDecision:
    """Non-interactive approval decision for one selected script binding."""

    status: SkillScriptApprovalStatus
    binding: SkillScriptApprovalBinding | None = None
    reason: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.reason is not None:
            _validate_bounded_observation_text(self.reason, field_name="reason")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def is_approved(self) -> bool:
        """Return whether this decision represents a positive approval."""
        return self.status is SkillScriptApprovalStatus.APPROVED


@dataclass(frozen=True, slots=True)
class SkillScriptSandboxPolicy:
    """Declarative sandbox policy intent for future script execution."""

    timeout_seconds: int = DEFAULT_SKILL_SCRIPT_TIMEOUT_SECONDS
    allow_network: bool = False
    writable_path_labels: tuple[str, ...] = field(default_factory=tuple)
    environment_allowlist: tuple[str, ...] = field(default_factory=tuple)
    max_stdout_chars: int = DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS
    max_stderr_chars: int = DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS
    max_script_bytes: int = DEFAULT_MAX_SKILL_SCRIPT_BYTES

    def __post_init__(self) -> None:
        _validate_positive_int(self.timeout_seconds, field_name="timeout_seconds")
        _validate_non_negative_int(self.max_stdout_chars, field_name="max_stdout_chars")
        _validate_non_negative_int(self.max_stderr_chars, field_name="max_stderr_chars")
        _validate_positive_int(self.max_script_bytes, field_name="max_script_bytes")
        writable_path_labels = tuple(self.writable_path_labels)
        environment_allowlist = tuple(self.environment_allowlist)
        for label in writable_path_labels:
            _validate_safe_script_text(label, field_name="writable_path_labels")
        if len(environment_allowlist) > DEFAULT_MAX_SKILL_SCRIPT_ENVIRONMENT_NAMES:
            msg = "environment allowlist exceeds the default deny-by-default bound"
            raise ValueError(msg)
        for name in environment_allowlist:
            _validate_environment_name(name)
        object.__setattr__(self, "writable_path_labels", writable_path_labels)
        object.__setattr__(self, "environment_allowlist", environment_allowlist)


@dataclass(frozen=True, slots=True)
class SkillScriptPolicyEvaluationCommand:
    """Application command for evaluating one selected script against policy."""

    selection: SelectedSkillScript
    sandbox_policy: SkillScriptSandboxPolicy = field(default_factory=SkillScriptSandboxPolicy)


@dataclass(frozen=True, slots=True)
class SkillScriptExecutionCommand:
    """Application command for executing one selected script after policy approval."""

    selection: SelectedSkillScript
    sandbox_policy: SkillScriptSandboxPolicy = field(default_factory=SkillScriptSandboxPolicy)


@dataclass(frozen=True, slots=True)
class SkillScriptExecutionOutput:
    """Bounded captured script output safe for application results."""

    text: str = ""
    truncated: bool = False
    max_chars: int = DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.max_chars, field_name="max_chars")
        if len(self.text) > self.max_chars:
            msg = "script execution output exceeds its declared bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SkillScriptPolicyObservation:
    """Privacy-safe diagnostic observation for script policy evaluation."""

    message: str
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_bounded_observation_text(self.message, field_name="message")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SkillScriptExecutionObservation:
    """Privacy-safe diagnostic observation for script execution."""

    message: str
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_bounded_observation_text(self.message, field_name="message")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SkillScriptPolicyEvaluationResult:
    """Normalized, application-safe result for selected script policy evaluation."""

    status: SkillScriptPolicyStatus
    selection: SelectedSkillScript
    binding: SkillScriptApprovalBinding | None = None
    observations: tuple[SkillScriptPolicyObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))

    @property
    def approved(self) -> bool:
        """Return whether the selected script is approved by policy."""
        return self.status is SkillScriptPolicyStatus.APPROVED


@dataclass(frozen=True, slots=True)
class SkillScriptExecutionResult:
    """Normalized, application-safe result for selected script execution."""

    status: SkillScriptExecutionStatus
    selection: SelectedSkillScript
    binding: SkillScriptApprovalBinding | None = None
    stdout: SkillScriptExecutionOutput = field(default_factory=SkillScriptExecutionOutput)
    stderr: SkillScriptExecutionOutput = field(default_factory=SkillScriptExecutionOutput)
    exit_code: int | None = None
    duration_seconds: float | None = None
    observations: tuple[SkillScriptExecutionObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.binding is not None and (
            self.selection.skill_id != self.binding.skill_id or self.selection.script_id != self.binding.script_id
        ):
            msg = "script execution binding must match the selected script"
            raise ValueError(msg)
        if self.duration_seconds is not None and self.duration_seconds < 0:
            msg = "duration_seconds must not be negative"
            raise ValueError(msg)
        object.__setattr__(self, "observations", tuple(self.observations))

    @property
    def succeeded(self) -> bool:
        """Return whether script execution completed successfully."""
        return self.status is SkillScriptExecutionStatus.SUCCESS


def skill_script_type_for_suffix(suffix: str) -> SkillScriptType | None:
    """Return the supported script type for a suffix, if policy recognizes it."""
    normalized_suffix = suffix.lower()
    if normalized_suffix == ".py":
        return SkillScriptType.PYTHON
    if normalized_suffix == ".sh":
        return SkillScriptType.SHELL
    return None


def _validate_safe_skill_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS:
        msg = f"{field_name} exceeds the safe skill label bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if value.startswith("/") or "//" in value:
        msg = f"{field_name} must be a relative identifier"
        raise ValueError(msg)
    if any(part in {"", ".", ".."} for part in value.split("/")):
        msg = f"{field_name} must not contain traversal segments"
        raise ValueError(msg)
    if any(character not in SAFE_SKILL_LABEL_CHARS for character in value):
        msg = f"{field_name} contains unsupported characters"
        raise ValueError(msg)


def _validate_safe_script_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS:
        msg = f"{field_name} exceeds the safe script label bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if value.startswith("/") or "//" in value:
        msg = f"{field_name} must be a relative script identifier"
        raise ValueError(msg)
    if any(part in {"", ".", ".."} for part in value.split("/")):
        msg = f"{field_name} must not contain traversal segments"
        raise ValueError(msg)
    if any(character not in SAFE_SKILL_LABEL_CHARS for character in value):
        msg = f"{field_name} contains unsupported characters"
        raise ValueError(msg)


def _validate_supported_suffix(suffix: str) -> None:
    if suffix.lower() not in SUPPORTED_SKILL_SCRIPT_SUFFIXES:
        msg = "script suffix is not supported"
        raise ValueError(msg)


def _validate_content_digest(content_digest: str) -> None:
    if not content_digest:
        msg = "content_digest must not be empty"
        raise ValueError(msg)
    if len(content_digest) > DEFAULT_MAX_SKILL_SCRIPT_DIGEST_CHARS:
        msg = "content_digest exceeds the safe digest bound"
        raise ValueError(msg)
    if content_digest != content_digest.strip():
        msg = "content_digest must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:-_"
        for character in content_digest
    ):
        msg = "content_digest contains unsupported characters"
        raise ValueError(msg)


def _validate_environment_name(value: str) -> None:
    if not value:
        msg = "environment name must not be empty"
        raise ValueError(msg)
    if value[0].isdigit():
        msg = "environment name must not start with a digit"
        raise ValueError(msg)
    if any(character not in SAFE_ENVIRONMENT_NAME_CHARS for character in value):
        msg = "environment name contains unsupported characters"
        raise ValueError(msg)


def _validate_bounded_observation_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SKILL_SCRIPT_OBSERVATION_MESSAGE_CHARS:
        msg = f"{field_name} exceeds the safe observation bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)


def _validate_positive_int(value: int, *, field_name: str) -> None:
    if value < 1:
        msg = f"{field_name} must be at least 1"
        raise ValueError(msg)


def _validate_non_negative_int(value: int, *, field_name: str) -> None:
    if value < 0:
        msg = f"{field_name} must not be negative"
        raise ValueError(msg)
