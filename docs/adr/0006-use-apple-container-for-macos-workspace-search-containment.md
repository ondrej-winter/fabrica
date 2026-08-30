# 0006. Use Apple Container for macOS Workspace Search Containment

Date: 2026-08-29
Status: Superseded by [0007](./0007-use-native-macos-ripgrep-with-explicit-best-effort-containment.md)

Supersedes the macOS mechanism in [0005](./0005-pin-workspace-search-subprocess-containment.md).

> **Supersession note:** On August 30, 2026, ADR 0007 replaced this decision.
> Apple Container imposed an unacceptable end-user setup requirement for ordinary
> local workspace search. The historical context below explains why this stronger
> containment approach was selected before that product decision.

## Context

`search_codebase` launches ripgrep as a recursive external process. Resolving a
scope before launch cannot prevent a later pathname or symlink replacement from
making that process read outside the configured workspace.

ADR 0005 selected the deprecated `/usr/bin/sandbox-exec` command for macOS. On
macOS Apple Silicon, the checksum-verified native ripgrep binary aborts under the
deny-by-default profile required to expose only its runtime dependencies and the
workspace. Broadening that profile enough for ripgrep to run would expose ambient
host paths and weaken the required containment guarantee.

Linux Bubblewrap already provides a namespace-backed, read-only workspace mount.
macOS needs an equivalent lifecycle-long boundary for an arbitrary search process
without host-ripgrep discovery or an unsandboxed fallback.

## Decision

Use platform-specific containment implementations behind the
`workspace_searching` outbound boundary:

- Linux `x86_64` continues to execute the checksum-verified package-data ripgrep
  executable inside Bubblewrap, with the workspace mounted read-only at
  `/workspace`.
- macOS Apple Silicon on macOS 26 or later executes a Fabrica-distributed,
  digest-verified OCI search image through the Apple `container` CLI. The runtime
  mounts only the canonical workspace root read-only at `/workspace`; the backend
  receives only the corresponding `/workspace/<relative-scope>` path.
- The macOS search image must be provisioned locally before tool invocation from
  a Fabrica-distributed OCI archive or an equivalent explicit operator workflow.
  The tool must not pull an image from a registry during a search call.
- The macOS container root filesystem must be read-only. The backend must not
  inherit ambient host environment values, attach host paths other than the
  workspace, attach a network, discover host ripgrep, or use a fallback regex
  engine.
- Missing, unhealthy, unsupported, or unverifiable containment runtimes or
  payloads fail closed as `SEARCH_BACKEND_UNAVAILABLE` before backend execution.

The pinned-ripgrep adapter owns fixed command construction, process supervision,
cancellation, timeout cleanup, and output parsing. It must not expose arbitrary
container execution.

## Consequences

- macOS support now requires Apple Silicon, macOS 26 or later, a compatible
  installed Apple `container` CLI and healthy local container service, plus the
  verified locally provisioned Fabrica search image.
- The macOS payload is a digest-pinned OCI image rather than a native macOS
  package-data executable. Linux continues to use its package-data executable.
- The application contracts, canonical paths, ripgrep arguments, JSON event
  parsing, result formatting, and error taxonomy remain backend-neutral.
- macOS conformance coverage must verify read-only workspace mounting, absence of
  ambient host-path mounts, image digest verification, no automatic registry pull,
  post-resolution symlink-race containment, and cleanup on result cap,
  cancellation, and timeout.
- Release validation must run the Linux Bubblewrap backend on Linux `x86_64` and
  the Apple Container backend on macOS Apple Silicon. A wheel/source distribution
  check alone is insufficient for the macOS image payload.

## Alternatives considered

| Option | Reason rejected |
| --- | --- |
| Retain `sandbox-exec` | It is deprecated and the required narrow profile aborts the verified native ripgrep binary. |
| Broaden the `sandbox-exec` profile | Allowing ambient host reads defeats workspace-only containment. |
| Run native ripgrep without an OS boundary | A recursive external process can observe post-validation filesystem races. |
| Use Docker Desktop as the canonical backend | It adds a third-party daemon and host file-sharing configuration rather than a selected Apple platform containment mechanism. |
