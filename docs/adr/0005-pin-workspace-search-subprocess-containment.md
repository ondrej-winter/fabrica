# 0005. Pin Workspace Search Subprocess Containment

Date: 2026-08-28
Status: Superseded by [0006](./0006-use-apple-container-for-macos-workspace-search-containment.md)

## Context

`search_codebase` must prevent a backend traversal from escaping the configured
workspace for its whole process lifetime. A lexical path check or a
`Path.resolve()` check made before process launch cannot protect against a
pathname or symlink replacement after validation.

## Decision

The `workspace_searching` POSIX adapter resolves literal scopes only for request
classification and then requires an OS sandbox wrapper for every backend launch.

- macOS requires `/usr/bin/sandbox-exec` with a generated deny-by-default profile
  that allows the verified backend, required system runtime libraries, and the
  configured workspace read access.
- Linux requires Bubblewrap. It creates a new namespace and exposes the workspace
  only as a read-only bind mount at `/workspace`; the backend receives that
  sandbox-local scope path.
- Other platforms, missing sandbox executables, or invalid containment inputs fail
  closed before backend launch.

The pinned ripgrep adapter introduced in the next task will own process
supervision, cancellation, and backend argument construction. It may use this
boundary only with a verified packaged executable and fixed arguments; it must
not expose an arbitrary process API.

## Consequences

- Search scope validation rejects paths outside the workspace, missing paths,
  special files, and recursive directory symlinks. Explicit symlinked files are
  canonicalized only when they resolve inside the workspace.
- The search implementation has no host-ripgrep fallback when containment is
  unavailable.
- macOS and Linux integration/conformance coverage must verify that a filesystem
  replacement after planning cannot make backend traversal read an outside path.

## Alternatives considered

| Option | Reason rejected |
| --- | --- |
| Resolve path then invoke ripgrep directly | A post-validation replacement race can escape the workspace. |
| Reuse descriptor-only file-open logic | A descriptor protects one opened file, not ripgrep's recursive traversal tree. |
| Discover a host sandbox or fall back to unsandboxed search | It changes safety guarantees across machines and fails the accepted contract. |

## Supersession note

ADR 0006 supersedes this decision's macOS `sandbox-exec` mechanism. The Linux
Bubblewrap mechanism and the lifecycle-long containment requirement remain in
effect.
