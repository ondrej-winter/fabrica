"""Immutable DTOs for the live user-interaction application boundary."""

from dataclasses import dataclass
from enum import StrEnum
from secrets import token_urlsafe

MAX_QUESTION_ID_CHARS = 120
MAX_QUESTION_CHARS = 4_000
MAX_OPTION_CHARS = 500
MIN_OPTIONS = 2
MAX_OPTIONS = 5
QUESTION_ID_PREFIX = "q_"


class InteractionErrorCode(StrEnum):
    """Stable Version 1 error codes for live user interactions."""

    INVALID_INPUT = "INVALID_INPUT"
    QUESTION_ALREADY_PENDING = "QUESTION_ALREADY_PENDING"
    INTERACTION_PUBLISH_FAILED = "INTERACTION_PUBLISH_FAILED"
    SESSION_NOT_INTERACTIVE = "SESSION_NOT_INTERACTIVE"
    INTERACTION_NOT_FOUND = "INTERACTION_NOT_FOUND"
    INTERNAL_INTERACTION_ERROR = "INTERNAL_INTERACTION_ERROR"


class InteractionState(StrEnum):
    """In-memory lifecycle states for one interaction record."""

    PENDING = "pending"
    ANSWERED = "answered"
    CANCELLED = "cancelled"


class InteractionResultStatus(StrEnum):
    """Terminal Version 1 interaction result statuses."""

    ANSWERED = "answered"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class QuestionId:
    """Opaque identifier linking a published question to its terminal result."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith(QUESTION_ID_PREFIX):
            msg = "question_id must start with `q_`"
            raise ValueError(msg)
        if len(self.value) > MAX_QUESTION_ID_CHARS:
            msg = "question_id exceeds the safe length bound"
            raise ValueError(msg)
        if (
            len(self.value) == len(QUESTION_ID_PREFIX)
            or not self.value.isascii()
            or not self.value[len(QUESTION_ID_PREFIX) :].replace("_", "").replace("-", "").isalnum()
        ):
            msg = "question_id must contain only opaque URL-safe identifier characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class InteractionOwner:
    """Opaque host-owned identity used to authorize one live interaction run."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.isascii() or not self.value.replace("_", "").replace("-", "").isalnum():
            msg = "interaction owner must be a non-empty opaque identifier"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class InteractionQuestion:
    """One validated focused question with its suggested free-text answers."""

    question: str
    options: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_whitespace_text(self.question, field_name="question", max_chars=MAX_QUESTION_CHARS)
        object.__setattr__(self, "options", tuple(self.options))
        if not MIN_OPTIONS <= len(self.options) <= MAX_OPTIONS:
            msg = f"options must contain between {MIN_OPTIONS} and {MAX_OPTIONS} entries"
            raise ValueError(msg)
        for option in self.options:
            _validate_non_whitespace_text(option, field_name="option", max_chars=MAX_OPTION_CHARS)
        if len(set(self.options)) != len(self.options):
            msg = "options must be exact-unique"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class InteractionPublication:
    """Structured host event that publishes one question idempotently."""

    question_id: QuestionId
    question: InteractionQuestion


@dataclass(frozen=True, slots=True)
class AnswerSubmission:
    """Host-supplied attempted answer without interaction-owner information."""

    question_id: QuestionId
    answer: str
    selected_option: int | None = None

    def __post_init__(self) -> None:
        _validate_non_whitespace_text(self.answer, field_name="answer", max_chars=MAX_QUESTION_CHARS)
        _validate_selected_option(self.selected_option)


@dataclass(frozen=True, slots=True)
class InteractionResult:
    """Terminal answer or cancellation result for one published question."""

    question_id: QuestionId
    status: InteractionResultStatus
    answer: str | None
    selected_option: int | None = None

    def __post_init__(self) -> None:
        if self.status is InteractionResultStatus.ANSWERED:
            if self.answer is None:
                msg = "answered interactions require a non-empty answer"
                raise ValueError(msg)
            _validate_non_whitespace_text(self.answer, field_name="answer", max_chars=MAX_QUESTION_CHARS)
            _validate_selected_option(self.selected_option)
            return
        if self.answer is not None or self.selected_option is not None:
            msg = "cancelled interactions require null answer and selected_option"
            raise ValueError(msg)


def generate_question_id() -> QuestionId:
    """Generate an opaque Version 1 question identifier."""
    return QuestionId(value=f"{QUESTION_ID_PREFIX}{token_urlsafe(24)}")


def _validate_non_whitespace_text(value: str, *, field_name: str, max_chars: int) -> None:
    if not isinstance(value, str):
        msg = f"{field_name} must be a string"
        raise TypeError(msg)
    if not value.strip():
        msg = f"{field_name} must contain a non-whitespace character"
        raise ValueError(msg)
    if len(value) > max_chars:
        msg = f"{field_name} exceeds the safe length bound"
        raise ValueError(msg)


def _validate_selected_option(selected_option: int | None) -> None:
    if selected_option is None:
        return
    if isinstance(selected_option, bool) or not isinstance(selected_option, int) or selected_option < 0:
        msg = "selected_option must be a zero-based option index or null"
        raise ValueError(msg)
