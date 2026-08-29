"""Tests for canonical workspace-searching result payloads."""

from fabrica.features.workspace_searching.application.dtos import (
    SearchCodebaseResult,
    SearchContextLine,
    SearchError,
    SearchErrorCode,
    SearchMatch,
    SearchQuery,
    SearchQueryFailure,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.result_formatting import search_codebase_result_payload


def test_search_codebase_result_payload_preserves_success_failure_and_context_contracts() -> None:
    query = SearchQuery(pattern="UserService", path="src", glob="**/*.py", case_sensitive=True)
    result = SearchCodebaseResult(
        (
            SearchQuerySuccess(
                query=query,
                matches=(
                    SearchMatch(
                        path="src/service.py",
                        line=4,
                        column=2,
                        text="    UserService()",
                        text_truncated=False,
                        before=(SearchContextLine(line=3, text=""),),
                        after=(SearchContextLine(line=5, text="pass", text_truncated=True),),
                    ),
                ),
            ),
            SearchQueryFailure(
                query=query,
                error=SearchError(SearchErrorCode.INVALID_REGEX, message="invalid regex"),
            ),
        )
    )

    assert search_codebase_result_payload(result) == {
        "results": [
            {
                "query": {"pattern": "UserService", "path": "src", "glob": "**/*.py", "case_sensitive": True},
                "success": True,
                "matches": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "column": 2,
                        "text": "    UserService()",
                        "text_truncated": False,
                        "before": [{"line": 3, "text": "", "text_truncated": False}],
                        "after": [{"line": 5, "text": "pass", "text_truncated": True}],
                    }
                ],
                "matches_returned": 1,
                "limit_reached": False,
                "output_truncated": False,
                "output_omitted": False,
                "reason": None,
                "more_results_possible": False,
            },
            {
                "query": {"pattern": "UserService", "path": "src", "glob": "**/*.py", "case_sensitive": True},
                "success": False,
                "error": {"code": "INVALID_REGEX", "message": "invalid regex", "metadata": {}},
            },
        ]
    }
