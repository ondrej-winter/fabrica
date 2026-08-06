"""Parsers for staged git subprocess output."""

from __future__ import annotations

from fabrica.features.developer_workflow.application.dtos import GitStagedFile, GitStagedFileStatus

REGULAR_NAME_STATUS_FIELD_COUNT = 2
RENAME_COPY_NAME_STATUS_FIELD_COUNT = 3


def parse_name_status_line(line: str) -> GitStagedFile:
    """Parse one `git diff --name-status` line into staged file metadata."""
    fields = line.split("\t")
    if len(fields) < REGULAR_NAME_STATUS_FIELD_COUNT:
        msg = "staged name-status record must include status and path"
        raise ValueError(msg)
    status = GitStagedFileStatus(fields[0][0])
    if status in {GitStagedFileStatus.RENAMED, GitStagedFileStatus.COPIED}:
        if len(fields) != RENAME_COPY_NAME_STATUS_FIELD_COUNT:
            msg = "rename and copy records must include old and new paths"
            raise ValueError(msg)
        path = fields[2]
    elif len(fields) == REGULAR_NAME_STATUS_FIELD_COUNT:
        path = fields[1]
    else:
        msg = "staged name-status record has unexpected path fields"
        raise ValueError(msg)
    return GitStagedFile(path=path, status=status)
