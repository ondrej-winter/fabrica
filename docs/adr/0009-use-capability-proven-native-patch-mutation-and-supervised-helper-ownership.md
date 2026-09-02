# 0009. Use Capability-Proven Native Patch Mutation and Supervised Helper Ownership

Date: 2026-09-02
Status: Accepted

## Context

`apply_patch` must not mutate a workspace merely because its host identifies as
macOS or Linux. The production contract requires descriptor-rooted path
resolution, no-follow behavior, no-replace destination creation or rename,
durability barriers, and ownership of commit and cleanup after cancellation or
caller disconnect.

Python's standard library does not expose the required no-replace rename
primitive, and in-process execution cannot prove a hard cleanup deadline for
potentially blocking POSIX operations. The existing implementation therefore
remains fail-closed pending a selected backend and helper ownership model.

## Decision

Fabrica will enable production `apply_patch` only from positive capability
evidence gathered against the actual workspace. The evidence records the
platform, architecture, workspace device, filesystem type, selected backend,
and a result for every required primitive. Any unsupported or failed probe keeps
mutation disabled with `UNSUPPORTED_FILESYSTEM_GUARANTEE` before mutation.

The selected native and ownership designs are:

- **macOS Apple Silicon:** use `renameatx_np(fromfd, from, tofd, to, flags)` via
  a narrow adapter-private binding, with `RENAME_EXCL` and
  `RENAME_NOFOLLOW_ANY`; enable it only after an actual-workspace filesystem
  probe proves those flags provide the required semantics.
- **Linux:** use `renameat2(..., RENAME_NOREPLACE)` through a narrow
  adapter-private syscall binding only after a per-filesystem proof. Linux is a
  candidate, not a release-blocking prerequisite for the primary macOS target.
- **Traversal and durability:** open the workspace root and descendants through
  pinned directory descriptors, reject symlink traversal, revalidate identities
  immediately before visible effects, and fsync durable journal/file/directory
  state at the lifecycle barriers defined by ADR 0003.
- **Ownership:** execute each visible preparation, commit, rollback, and cleanup
  operation in a short-lived, per-operation supervised helper. Before the first
  visible effect, the helper reopens and validates durable plan/journal state.
  The parent reports success only after journal-backed terminal evidence. IPC
  loss, helper crash, cancellation, deadline expiry, or unproven termination
  returns an indeterminate or recovery-required outcome; the host never claims a
  terminal mutation result while an unmanaged helper may continue.

AP-01 records this architecture but does not enable either backend. AP-02 must
prove descriptor-rooted native no-replace behavior, and AP-03 must prove helper
terminal-state and termination guarantees.

## Consequences

- Production mutation remains fail-closed until all actual-workspace evidence is
  positive after AP-02 and AP-03.
- Platform or filesystem names, feature flags, and successful planning are never
  sufficient to enable mutation.
- Native bindings and helper IPC remain adapter-private; application ports expose
  only typed patch results and do not leak OS handles or FFI details.
- Unsupported Linux filesystem/backend combinations must remain explicitly
  unsupported rather than falling back to ordinary replace-capable rename APIs.
- Startup recovery must take ownership when a helper cannot prove a terminal
  journal state.

## Alternatives considered

| Option | Reason rejected |
| --- | --- |
| Use `os.rename` or `os.replace` after an existence check | A concurrent destination creator can be overwritten; the required no-replace guarantee is absent. |
| Enable by platform or filesystem name | Names do not prove the selected primitive or helper ownership works for the actual workspace. |
| Run visible mutation in the host process | A host cancellation or deadline cannot prove bounded cleanup for blocking POSIX operations. |
| Delay all design work until a cross-platform backend exists | It would delay the primary Apple Silicon macOS target and leave unsupported Linux combinations ambiguous. |
