# 0007. Use Native macOS Ripgrep With Explicit Best-Effort Containment

Date: 2026-08-30
Status: Superseded by [0008](./0008-use-native-ripgrep-with-best-effort-containment-on-supported-platforms.md)

Supersedes [0006](./0006-use-apple-container-for-macos-workspace-search-containment.md).

## Context

`search_codebase` must work as an ordinary local developer tool. ADR 0006 selected
Apple Container plus a locally provisioned OCI image to preserve lifecycle-long
workspace containment for macOS recursive search. That approach requires users to
install and operate a separate container runtime and provision an image before
search can work.

Those prerequisites are disproportionate for read-only source discovery and make
the macOS product experience materially worse than a normal Fabrica installation.
The project still must not discover or fall back to a host-installed `rg`, change
the regex engine, invoke a shell, or silently overstate its filesystem safety
guarantees.

## Decision

Fabrica will distribute a checksum-verified, pinned native `ripgrep` executable
as package data for macOS Apple Silicon, alongside the existing Linux `x86_64`
package-data executable.

- macOS search must require no Apple Container, OCI image, daemon, image pull, or
  host-installed ripgrep.
- Before direct native execution, Fabrica validates the requested literal
  workspace-relative scope, rejects absolute paths, traversal, missing targets,
  special files, and resolved symlink escapes, and invokes the verified executable
  with fixed argv, `--no-config`, and `--no-follow`.
- This direct macOS execution is **best-effort pre-launch containment**. It does
  not guarantee that a malicious concurrent local process cannot replace a path or
  symlink after validation and before or during ripgrep traversal.
- Linux retains Bubblewrap and its lifecycle-long read-only `/workspace` mount.
- Unsupported platforms and missing, malformed, unexecutable, or checksum-invalid
  Fabrica payloads fail closed with `SEARCH_BACKEND_UNAVAILABLE`.

## Consequences

- macOS Apple Silicon users receive a smooth package-only search experience once
  the native artifact is shipped.
- The specification, implementation plan, tests, and README must distinguish
  Linux's lifecycle-long containment from macOS best-effort containment; no
  macOS race-proof guarantee may remain.
- macOS release conformance moves from Apple Container/image checks to clean
  wheel/source-distribution installation, executable permission, checksum,
  pinned-version, representative search, and ordinary symlink-escape regression
  checks.
- The direct native backend is acceptable for a developer-controlled workspace,
  not for a hostile multi-tenant filesystem or a threat model requiring resistance
  to concurrent workspace mutation.
- A future descriptor-rooted native helper may restore stronger macOS containment
  without an external runtime. Its evaluation and acceptance bar are recorded in
  [`../future-work/descriptor-rooted-search-helper.md`](../future-work/descriptor-rooted-search-helper.md).

## Alternatives considered

| Option | Reason rejected or deferred |
| --- | --- |
| Retain Apple Container and a local OCI image | Strong containment, but unacceptable installation, service, and image-provisioning friction for normal local search. |
| Native descriptor-rooted Fabrica search helper | Potentially restores strong containment without a runtime prerequisite, but requires a separately designed and security-reviewed native component. |
| Discover or use host-installed ripgrep | Makes semantics, versioning, and trust vary by host. |
| Python regex fallback | Changes regex and ignore semantics and cannot preserve the pinned-ripgrep contract. |
