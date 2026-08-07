"""Tool definitions for read-only git context inspection."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import ToolArgumentSchemaValue, ToolDefinition

GIT_STATUS_SUMMARY_TOOL_NAME = "git_status_summary"
GIT_UNSTAGED_FILES_TOOL_NAME = "git_unstaged_files"
GIT_UNSTAGED_DIFF_TOOL_NAME = "git_unstaged_diff"
GIT_UNSTAGED_FILE_DIFF_TOOL_NAME = "git_unstaged_file_diff"
GIT_COMMIT_LOG_TOOL_NAME = "git_commit_log"
GIT_COMMIT_DETAILS_TOOL_NAME = "git_commit_details"
GIT_COMMIT_CHANGED_FILES_TOOL_NAME = "git_commit_changed_files"
GIT_COMMIT_DIFF_TOOL_NAME = "git_commit_diff"
GIT_COMMIT_FILE_DIFF_TOOL_NAME = "git_commit_file_diff"
GIT_REF_CHANGED_FILES_TOOL_NAME = "git_ref_changed_files"
GIT_REF_DIFF_TOOL_NAME = "git_ref_diff"
GIT_REF_FILE_DIFF_TOOL_NAME = "git_ref_file_diff"
GIT_BRANCH_AHEAD_BEHIND_TOOL_NAME = "git_branch_ahead_behind"
GIT_MERGE_BASE_TOOL_NAME = "git_merge_base"

_EMPTY_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
_PATH_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": (
                "Relative path of a changed file to inspect. Must be listed by the matching changed-files tool."
            ),
        },
    },
    "required": ("path",),
    "additionalProperties": False,
}
_COUNT_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "count": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "description": "Maximum number of recent commits to return. Defaults to a small configured count.",
        },
    },
    "additionalProperties": False,
}
_COMMIT_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {"commit": {"type": "string", "description": "Commit-ish to inspect as a commit object."}},
    "required": ("commit",),
    "additionalProperties": False,
}
_COMMIT_PATH_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "commit": {"type": "string", "description": "Commit-ish to inspect as a commit object."},
        "path": {
            "type": "string",
            "description": "Relative path changed by the commit. Must be listed by git_commit_changed_files.",
        },
    },
    "required": ("commit", "path"),
    "additionalProperties": False,
}
_REF_PAIR_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "base_ref": {"type": "string", "description": "Base git ref for the comparison."},
        "head_ref": {"type": "string", "description": "Head git ref for the comparison."},
    },
    "required": ("base_ref", "head_ref"),
    "additionalProperties": False,
}
_REF_PAIR_PATH_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "base_ref": {"type": "string", "description": "Base git ref for the comparison."},
        "head_ref": {"type": "string", "description": "Head git ref for the comparison."},
        "path": {
            "type": "string",
            "description": "Relative path changed between refs. Must be listed by git_ref_changed_files.",
        },
    },
    "required": ("base_ref", "head_ref", "path"),
    "additionalProperties": False,
}
_AHEAD_BEHIND_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "base_ref": {
            "type": "string",
            "description": "Optional base ref. Defaults to the current branch upstream when omitted.",
        },
    },
    "additionalProperties": False,
}

GIT_STATUS_SUMMARY_TOOL_DEFINITION = ToolDefinition(
    name=GIT_STATUS_SUMMARY_TOOL_NAME,
    description="Return a bounded summary of the current git worktree state without raw diffs.",
    argument_schema=_EMPTY_ARGUMENT_SCHEMA,
)
GIT_UNSTAGED_FILES_TOOL_DEFINITION = ToolDefinition(
    name=GIT_UNSTAGED_FILES_TOOL_NAME,
    description="List tracked files with unstaged git changes and their statuses.",
    argument_schema=_EMPTY_ARGUMENT_SCHEMA,
)
GIT_UNSTAGED_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_UNSTAGED_DIFF_TOOL_NAME,
    description="Return the bounded full unstaged git diff for tracked files.",
    argument_schema=_EMPTY_ARGUMENT_SCHEMA,
)
GIT_UNSTAGED_FILE_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_UNSTAGED_FILE_DIFF_TOOL_NAME,
    description="Return the bounded unstaged git diff for one tracked changed file path.",
    argument_schema=_PATH_ARGUMENT_SCHEMA,
)
GIT_COMMIT_LOG_TOOL_DEFINITION = ToolDefinition(
    name=GIT_COMMIT_LOG_TOOL_NAME,
    description="List recent commits with bounded metadata and no raw diffs.",
    argument_schema=_COUNT_ARGUMENT_SCHEMA,
)
GIT_COMMIT_DETAILS_TOOL_DEFINITION = ToolDefinition(
    name=GIT_COMMIT_DETAILS_TOOL_NAME,
    description="Return metadata and message details for one validated commit without raw diff output.",
    argument_schema=_COMMIT_ARGUMENT_SCHEMA,
)
GIT_COMMIT_CHANGED_FILES_TOOL_DEFINITION = ToolDefinition(
    name=GIT_COMMIT_CHANGED_FILES_TOOL_NAME,
    description="List paths and statuses changed by one validated commit without raw diff output.",
    argument_schema=_COMMIT_ARGUMENT_SCHEMA,
)
GIT_COMMIT_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_COMMIT_DIFF_TOOL_NAME,
    description="Return the bounded full diff for one validated commit.",
    argument_schema=_COMMIT_ARGUMENT_SCHEMA,
)
GIT_COMMIT_FILE_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_COMMIT_FILE_DIFF_TOOL_NAME,
    description="Return the bounded diff for one file changed by one validated commit.",
    argument_schema=_COMMIT_PATH_ARGUMENT_SCHEMA,
)
GIT_REF_CHANGED_FILES_TOOL_DEFINITION = ToolDefinition(
    name=GIT_REF_CHANGED_FILES_TOOL_NAME,
    description="List paths and statuses changed between two validated refs without raw diff output.",
    argument_schema=_REF_PAIR_ARGUMENT_SCHEMA,
)
GIT_REF_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_REF_DIFF_TOOL_NAME,
    description="Return the bounded full diff between two validated refs.",
    argument_schema=_REF_PAIR_ARGUMENT_SCHEMA,
)
GIT_REF_FILE_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_REF_FILE_DIFF_TOOL_NAME,
    description="Return the bounded diff for one file changed between two validated refs.",
    argument_schema=_REF_PAIR_PATH_ARGUMENT_SCHEMA,
)
GIT_BRANCH_AHEAD_BEHIND_TOOL_DEFINITION = ToolDefinition(
    name=GIT_BRANCH_AHEAD_BEHIND_TOOL_NAME,
    description=(
        "Return current branch ahead and behind counts against upstream or an explicit base ref without fetching."
    ),
    argument_schema=_AHEAD_BEHIND_ARGUMENT_SCHEMA,
)
GIT_MERGE_BASE_TOOL_DEFINITION = ToolDefinition(
    name=GIT_MERGE_BASE_TOOL_NAME,
    description="Return the merge-base hashes for two validated refs.",
    argument_schema=_REF_PAIR_ARGUMENT_SCHEMA,
)
