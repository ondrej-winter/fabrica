# Module structure and file organization

Use these rules to keep files focused, navigable, and easy to maintain in a hexagonal codebase organized by vertical slices.
Use the `split-python-module` skill when a file or package needs a safe,
step-by-step split or reorganization.

## File size heuristics

- Treat line counts as review heuristics, not goals.
- **Should** consider splitting a file once it grows beyond ~300 lines or carries more than one clear responsibility.
- Files above ~500 lines **should** have an intentional reason to remain whole.
- Files above ~700 lines **should usually** be split or accompanied by a documented justification.

## Module organization principles

- **Should** prefer cohesion and clear ownership over arbitrary file-count targets.
- **Should** use packages when a concept has multiple responsibilities or is likely to expand.
- **Must** group feature behavior by business capability or use case before introducing broad global layer packages.
- **Should** group related classes and functions by responsibility inside the owning slice, not by type.
- **Should** keep one primary responsibility per file or module when splitting code.
- **Must** keep import side effects minimal; importing a module should not perform I/O, network calls, or heavyweight initialization.
- Adapter-specific structure should satisfy the architectural consistency expectations in `003-architecture-guardrails.md`.

## Feature slice package mechanics

- **Must** put new business capability code under `features/<feature_name>/` or the host project's documented equivalent.
- **Must** keep hexagonal responsibilities visible inside each slice with local `domain/`, `application/`, and `adapters/` packages when the slice needs those responsibilities.
- **Should** omit empty layer packages in very small slices until they are needed, but do not move behavior into the wrong layer just to avoid a directory.
- **Must** keep slice-private modules private by convention unless they are intentionally published through an inbound port, application API, domain event, or shared-kernel type.
- **Should** keep cross-slice shared domain concepts in `shared_kernel/` only when at least two slices genuinely need the same concept.
- **Must not** place mixed business behavior in top-level `common/`, `utils/`, or `services/` packages.

## Package and `__init__.py` conventions

- **Should** use `__init__.py` when you want a regular package or an intentional public package API.
- Namespace packages are acceptable only when chosen deliberately and documented.
- **Must** keep `__init__.py` lightweight; avoid wiring, I/O, or hidden runtime behavior in package imports.
- **Must not** import optional/heavy dependencies in `__init__.py` only to provide a shorter import path.
- **Should** re-export symbols only when providing a stable package-level API.
- **Should** use `__all__` when a module/package has a curated public surface or needs explicit star-import semantics; it is not required in every `__init__.py`.

## Naming conventions for split modules

- Module directory: `snake_case/` (e.g., `cli_adapter/`)
- Feature slice directory: `snake_case/` named by business capability (e.g., `features/report_generation/`)
- Main file: `adapter.py`, `service.py`, `writer.py`, etc. (semantic, not repetitive)
- Supporting files should prefer purpose-revealing names such as `validators.py`, `formatters.py`, `serialization.py`, `exceptions.py`, or similarly narrow modules.
- Avoid catch-all modules such as broad `utils.py`, `helpers.py`, or `common.py` unless the scope is intentionally tiny and local to the package.
- **Must** avoid redundant naming (use `cli_adapter/adapter.py`, not `cli_adapter/cli_adapter.py`).

## Adapter package mechanics

- **Must** keep sibling adapter categories internally consistent within the owning slice.
- **Should** use subdirectories when multiple adapters exist in the same parent directory or near-term expansion is likely.
- A single file is acceptable for a genuinely simple adapter with no near-term sibling adapters.
- **Must** name the main adapter implementation semantically, such as `adapter.py`, `parser.py`, `writer.py`, or `client.py`.
- **Must not** mix standalone files and subpackages within the same adapter category without a documented reason.
- Shared adapter infrastructure may live outside a slice only when it contains no business behavior and is wired through slice-owned ports.

## Splitting strategies

- When a split is warranted, separate modules by responsibility, domain concept,
  slice ownership, or layer concern rather than by arbitrary file-count targets.
- Use the `split-python-module` skill for concrete split sequencing, import
  preservation, and compatibility follow-up.

## Import management after splits

- **Should** prefer absolute imports across package boundaries.
- Within a small local package, either absolute or relative imports are acceptable; choose one style and keep it consistent.
- Preserve public import paths only when the package intentionally exposes a stable public API.
- **Must not** create deep multi-hop re-export chains or circular imports solely for convenience.
- When backward compatibility matters, update `__init__.py` or a dedicated compatibility module intentionally and document the surface.

## When NOT to split

- Files under 200 lines that are cohesive and focused: keep them as-is.
- Simple value objects, enums, or DTOs: group related ones together.
- Tightly coupled logic that would be harder to understand when separated.
- Stable leaf modules with a single clear responsibility and no growth pressure can remain whole even if they are not tiny.

## Intentional re-exports

- When exposing a stable package API, apply the `__init__.py` conventions above intentionally instead of re-exporting by default.
- Keep ownership visible; shorter imports are useful only when they do not create fragile or surprising import graphs.
