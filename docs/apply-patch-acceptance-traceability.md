# Apply Patch Acceptance Traceability

This document maps the v1 acceptance scenarios from
`docs/specs/apply-patch-tool.md` to the current test evidence for the
`workspace_editing` slice.

The implementation is intentionally incremental. Scenarios marked **Open** are
known remaining work and must stay visible until covered by focused tests or
explicitly deferred in the implementation plan.

## Summary

| Area | Current evidence |
| --- | --- |
| Basic operations | Covered for parser/planner and POSIX add, update, delete, move, and multi-file commit paths. |
| Grammar and matching | Covered by parser and deterministic hunk-matching unit tests. |
| Validation and paths | Covered for core duplicate/collision validation and POSIX path safety checks, including aliases, cross-device moves, and special-file classification. |
| Preservation | Covered for UTF-8/BOM/EOL rendering, POSIX mode preservation, and fail-closed rejection of nonzero POSIX file flags plus ACL/security extended attributes on action paths and existing destination parents. |
| Authorization and runtime behavior | Covered for policy/approval adapters, registered-tool result mapping, duplicate runtime delivery, and offline tool-loop composition. |
| Commit, rollback, recovery, and deadlines | Covered for deterministic commit order, stale-plan rejection, directory rollback/recovery, operator-gated commit recovery, durable file preimage rollback, and interruption recovery after each visible commit step. |

## Test evidence by scenario group

### Basic operations

- `tests/unit/features/workspace_editing/application/test_parse_patch.py` covers
  canonical Add, Update, Delete, Move, multi-file patches, zero-byte Add, and
  multi-hunk parse forms.
- `tests/unit/features/workspace_editing/application/test_plan_patch.py` covers
  operation planning, derived directory effects, commit-step ordering, and plan
  digest binding.
- `tests/integration/features/workspace_editing/test_posix_commit_adapter.py`
  covers POSIX staging and commit for Add, Update, Delete, Move, and mixed
  multi-file operation schedules.

### Grammar and matching

- `tests/unit/features/workspace_editing/application/test_parse_patch.py` covers
  canonical sentinels, invalid unprefixed lines, hunk directives, EOF assertion
  placement, no-op update rejection, and parser limits.
- `tests/unit/features/workspace_editing/application/test_match_hunks.py` covers
  exact matching, trailing-whitespace tolerance, source-context preservation,
  missing and ambiguous hunks, missing and ambiguous anchors, before/after
  insertion-only hunks, plain unsafe insertion-only hunks, overlapping and
  reverse-order hunks, and EOF assertion failures.

### Validation and paths

- `tests/unit/features/workspace_editing/application/test_plan_patch.py` covers
  duplicate source actions, destination collisions, move chains, move swaps, and
  derived parent-directory deduplication.
- `tests/integration/features/workspace_editing/test_posix_filesystem_snapshot_adapter.py`
  covers source/destination evidence collection, Add-target existence rejection,
  case/Unicode-normalization alias rejection, parent-file rejection, real FIFO and
  Unix-domain socket source/target rejection, real FIFO and Unix-domain socket
  parent rejection, synthetic character/block-device classification at action and
  parent boundaries, symlink path rejection, and multiple-hard-link and
  cross-device Move rejection.
- `tests/integration/features/workspace_editing/test_posix_commit_adapter.py`
  covers stale source content, stale source identity, changed destination parent,
  unexpected Add/Move destination appearance, missing staged payload, and changed
  staged payload mode before visible file commit.

### Preservation

- `tests/unit/features/workspace_editing/application/test_text_snapshot.py` covers
  UTF-8 versus UTF-8 BOM handling, LF and CRLF rendering, terminal-newline
  preservation, zero-byte file handling, invalid UTF-8, NUL bytes, mixed EOL, and
  bare CR rejection.
- `tests/integration/features/workspace_editing/test_posix_commit_adapter.py`
  covers Add default mode and Update/Move source-mode preservation in the current
  staged-payload path.
- `tests/integration/features/workspace_editing/test_posix_filesystem_snapshot_adapter.py`
  covers fail-closed rejection of nonzero POSIX file flags and ACL/security
  extended attributes on action paths and existing destination parents before
  staging or mutation, including a fail-closed result when extended attributes
  cannot be inspected. Unrelated host provenance xattrs are allowed. The
  staged-replacement path therefore never silently drops ACL-backed metadata.

### Authorization and runtime behavior

- `tests/unit/features/workspace_editing/adapters/outbound/authorization/test_adapter.py`
  covers protected path policy, stale approval, denied approval, approval timeout,
  unsafe missing preview rejection, and in-process lease serialization.
- `tests/unit/features/workspace_editing/adapters/inbound/registered_tool/test_adapter.py`
  covers the canonical `{ "input": string }` schema, model-facing description,
  invalid argument rejection, success mapping, recoverable rejection mapping, and
  fatal mutation-state mapping.
- `tests/unit/features/agent_runtime/application/test_run_tool_loop.py` covers
  duplicate tool-call replay, duplicate `call_id` argument conflicts, recoverable
  tool rejection continuation, and fatal tool outcomes.
- `tests/integration/features/workspace_editing/test_apply_patch_tool_composition.py`
  covers offline tool-loop composition for the explicitly injected apply-patch
  registered tool, committed output delivery, recoverable rejection continuation,
  and fatal mutation-state runtime stopping.
- **Open:** production default approval wiring remains blocked by platform
  capability evidence and is not exposed as an automatic default composition.

### Commit, rollback, recovery, and deadlines

- `tests/unit/features/workspace_editing/application/test_apply_patch.py` covers
  lease-to-commit phase ordering, update hunk matching before planning/staging,
  pre-journal and pre-commit policy rejection, capability rejection before
  parsing, parser rejection before snapshot, and rollback after file-staging or
  pre-commit policy rejection. It also proves that a terminal committer result
  with a missing or mismatched approved plan digest is converted to the fatal
  `INDETERMINATE_COMMIT_STATE` result rather than being reported as committed.
- `tests/integration/features/workspace_editing/test_posix_journal_preparation_adapter.py`
  covers durable intent before directory creation, preparation rollback after
  directory failure, incomplete-journal listing, and illegal transition rejection.
- `tests/integration/features/workspace_editing/test_posix_commit_adapter.py`
  covers deterministic commit execution, committed journal evidence, safe
  directory rollback, retained external directory content, automatic prepared
  journal recovery, durable file preimages/postimages, automatic committing-journal
  file rollback, retention of independently changed files, and injected staged-
  payload durability failures before the visible file commit point. It also
  injects an interruption after each durable visible Add, Update, Delete, and
  Move commit step, reloads the incomplete `COMMITTING` journal through a fresh
  adapter instance, and verifies evidence-proven rollback restores the original
  workspace.

## Platform support notes

- Production POSIX mutation remains fail-closed by default through
  `PosixPatchWorkspaceSnapshotAdapter(require_production_capabilities=True)`.
- Local macOS and Docker-based Linux POSIX capability evidence, including the
  reproducible commands and tested environment summaries, is recorded in
  `docs/apply-patch-posix-capability-evidence.md`.
- Production mutation still remains fail-closed until the open no-replace rename,
  supervised cleanup ownership, and remaining safety scenarios are implemented.
