# 0003. Use Journaled Reversible Workspace Mutation Lifecycle

Date: 2026-08-23
Status: Accepted

## Context

The v1 `apply_patch` contract automatically creates missing parent directories
for Add and Move destinations. Those directory creations are derived effects, not
model-authored actions, but they become visible before any file rename,
replacement, or deletion. Treating all pre-file-commit work as mutation-free would
make cancellation, rollback, and recovery guarantees untruthful.

The tool also must not claim cross-file atomicity. POSIX filesystems can support a
safe staged commit protocol, but multi-file mutation still needs journaled
best-effort commit, rollback, and explicit final-state evidence.

## Decision

`apply_patch` will use a four-phase workspace mutation lifecycle:

1. **Side-effect-free planning**: acquire the workspace mutation lease, parse,
   snapshot, match, derive effects, plan, evaluate policy, and obtain approval
   without mutating the filesystem.
2. **Reversible preparation**: after approval and revalidation, durably record
   recovery intent before any derived directory becomes visible. Create planned
   parent directories shallowest-first through pinned handles, record their
   identities, create staging artifacts, and prepare the journal.
3. **File commit**: immediately before the first visible file rename,
   replacement, or deletion, cross the explicit file commit point. Commit follows
   a deterministic planner-owned schedule and then performs required durability
   barriers.
4. **Cleanup and recovery**: remove stage artifacts and plan-created directories
   only when identity and emptiness checks prove it safe. While the process is
   active, the operation owns cleanup. After interruption or restart, startup
   recovery owns the remaining rollback or operator-facing recovery decision.

Created-directory outcomes are first-class result evidence. A no-mutation
guarantee is valid only when no visible effect occurred or all visible reversible
effects were proven removed. Retained, failed-to-remove, or uncertain directories
must be reported and must not be collapsed into a no-mutation rejection.

The documented mutation guarantee is:

```text
side-effect-free planning
+ journaled reversible preparation
+ best-effort file commit with explicit final-state reporting
```

This is intentionally not cross-file atomicity.

## Consequences

- The durable journal must contain metadata and recovery intent before any
  derived parent directory is created.
- Cancellation after visible directory creation cannot simply abort. It must enter
  bounded cleanup and report removed, retained, failed, or uncertain directory
  outcomes.
- Startup must block `apply_patch` exposure for a workspace with an incomplete
  journal until recovery proves rollback safe or marks the workspace
  `RECOVERY_REQUIRED`.
- Rollback and recovery must never remove plan-created directories unless identity
  and emptiness evidence proves they are still the same directories and contain no
  external work.
- The POSIX feasibility spike must still prove whether bounded in-process cleanup
  is credible on supported filesystems or whether a supervised helper-process
  ownership model is required.

## Alternatives considered

| Option | Reason rejected |
| ------ | --------------- |
| Treat derived directories as part of the file commit point | Directories are visible before file renames/deletes, so this would hide real mutation from cancellation and recovery semantics. |
| Reject Add and Move operations with missing destination parents | This would contradict the v1 product contract and make common patch operations unnecessarily brittle. |
| Claim cross-file atomicity through staging | POSIX multi-file commits still need best-effort scheduling, rollback, and final-state evidence. |
| Leave retained directories as harmless warnings | Retained directories are visible workspace mutations and must affect mutation guarantees and runtime disposition. |
