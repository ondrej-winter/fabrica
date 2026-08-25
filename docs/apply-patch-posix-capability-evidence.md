# Apply Patch POSIX Capability Evidence

This note records Task 5 evidence for `docs/plans/apply-patch-tool-plan.md`.
It is intentionally a feasibility artifact, not production `workspace_editing`
implementation.

## Probe command

Run on each supported platform from the repository root:

```text
uv run python scripts/apply_patch_posix_capability_probe.py --workspace .
```

The command emits compact JSON containing the platform, filesystem type, Python
version, per-primitive capability results, unsupported reasons, and the selected
design decision.

## Findings

- Python 3.13 standard library is sufficient for directory-handle-relative
  traversal, `O_NOFOLLOW` symlink rejection, exclusive create, pinned
  `st_dev`/`st_ino` identity evidence, link-count inspection, mode-bit
  inspection/application, regular-file/directory classification, regular-file
  `fsync`, and directory `fsync` on the probed POSIX filesystem.
- Python 3.13 standard library is not sufficient for a portable no-replace rename
  primitive. It exposes `os.rename` and `os.replace` with `dir_fd` support, but no
  portable `RENAME_NOREPLACE` or `renameat2` wrapper. Production code must add a
  platform-specific syscall/`ctypes` seam or choose a different pre-commit design
  before exposing mutation.
- A hard bounded in-process cleanup deadline cannot be proven for potentially
  blocking POSIX syscalls. The production design must use supervised
  helper-process/recovery ownership rather than claiming in-process cleanup is
  always bounded.
- Unsupported platforms and failed workspace filesystem probes must fail closed
  before mutation with `UNSUPPORTED_FILESYSTEM_GUARANTEE`.

## Local macOS evidence

Recorded on 2026-08-25 from this repository workspace:

```text
uv run python scripts/apply_patch_posix_capability_probe.py --workspace .
```

Summary:

- Platform: macOS (`darwin`), Python 3.13.
- Filesystem type: reported by `stat -f %T .` in the probe JSON.
- Supported through the standard library: traversal, no-follow open, exclusive
  create, pinned identities, link count, mode bits, file fsync, directory fsync,
  and file classification.
- Unsupported through the standard library: no-replace rename.
- Cleanup model decision: supervised helper-process/recovery ownership required.

## Local Docker Linux evidence

Run the standard-library-only probe in an ephemeral Linux container from the
repository root:

```text
docker run --rm \
  --mount type=bind,src="$(pwd)",dst=/workspace,readonly \
  --workdir /workspace \
  python:3.13-slim \
  python scripts/apply_patch_posix_capability_probe.py --workspace /tmp
```

Recorded on 2026-08-25 with `python:3.13-slim`:

- Platform: Linux (`linux`), Python 3.13.15, `aarch64`.
- Filesystem type: `overlayfs` for the container-owned `/tmp` probe workspace.
- Supported through the standard library: traversal, no-follow open, exclusive
  create, pinned identities, link count, mode bits, file fsync, directory fsync,
  and file classification.
- Unsupported through the standard library: no-replace rename.
- Cleanup model decision: supervised helper-process/recovery ownership required.

These platform checks are deliberately local rather than CI jobs. The repository
does not commit volatile probe JSON because kernel, filesystem, Docker runtime,
and host details can change. Production mutation remains fail-closed because the
probe intentionally reports the unresolved portable no-replace rename and
bounded-cleanup limitations.
