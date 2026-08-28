"""Tests for pure workspace-searching structural validation."""

import pytest

from fabrica.features.workspace_searching.application.dtos import SearchErrorCode, SearchQuery, SearchQueryFailure
from fabrica.features.workspace_searching.application.validation import ValidatedSearchBatch, validate_search_queries


def test_validation_applies_canonical_defaults_without_evaluating_regex_or_glob_grammar() -> None:
    validated = validate_search_queries(({"pattern": "[unfinished", "glob": "**/*.{py"},))

    query = validated.entries[0]
    assert isinstance(query, SearchQuery)
    assert query.path == "."
    assert query.glob == "**/*.{py"
    assert query.case_sensitive is False


def test_validation_preserves_independent_per_query_failures_in_input_order() -> None:
    validated = validate_search_queries(
        (
            {"pattern": "UserService", "path": "src"},
            {"pattern": "   "},
            {"pattern": 42},
            {"pattern": "Repository", "case_sensitive": True},
        )
    )

    assert isinstance(validated.entries[0], SearchQuery)
    assert isinstance(validated.entries[1], SearchQueryFailure)
    assert validated.entries[1].error.code is SearchErrorCode.EMPTY_PATTERN
    assert isinstance(validated.entries[2], SearchQueryFailure)
    assert validated.entries[2].error.code is SearchErrorCode.INVALID_INPUT
    assert isinstance(validated.entries[3], SearchQuery)
    assert validated.command is None


def test_validation_rejects_noncanonical_batch_shape_and_excessive_queries() -> None:
    with pytest.raises(TypeError, match="queries must be a tuple of canonical query objects"):
        validate_search_queries([{"pattern": "UserService"}])
    with pytest.raises(ValueError, match="must not be empty"):
        validate_search_queries(())
    with pytest.raises(ValueError, match="safe batch bound"):
        validate_search_queries(tuple({"pattern": "UserService"} for _ in range(9)))
    with pytest.raises(ValueError, match="must not be empty"):
        ValidatedSearchBatch(())


def test_validation_rejects_invalid_query_shapes_and_returns_an_executable_command_when_valid() -> None:
    validated = validate_search_queries(({"pattern": "UserService"},))
    assert validated.command is not None
    invalid_object = validate_search_queries(({"pattern": "UserService", "unknown": True},)).entries[0]
    missing_pattern = validate_search_queries(({},)).entries[0]
    invalid_path = validate_search_queries(({"pattern": "UserService", "path": 1},)).entries[0]

    assert isinstance(invalid_object, SearchQueryFailure)
    assert invalid_object.error.code is SearchErrorCode.INVALID_INPUT
    assert isinstance(missing_pattern, SearchQueryFailure)
    assert missing_pattern.error.code is SearchErrorCode.INVALID_INPUT
    assert isinstance(invalid_path, SearchQueryFailure)
    assert invalid_path.error.code is SearchErrorCode.INVALID_INPUT
