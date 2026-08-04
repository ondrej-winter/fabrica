# Universal coding standards: naming, formatting, error handling, logging

Use these rules for all Python code in the project to keep behavior predictable and reviews lightweight.

## Naming

- **Modules/files**: `snake_case.py` (e.g., `prompt_loader.py`).
- **Packages**: lowercase, no hyphens.
- **Classes**: `PascalCase` nouns (e.g., `ReportBuilder`).
- **Functions/methods**: `snake_case` verbs (e.g., `load_prompt`).
- **Constants**: `UPPER_SNAKE_CASE`.
- **Tests**: `test_<behavior>()` focused on the behavior under test.

## Formatting

- Use the `format-python-code` skill to apply auto-fixes and format the codebase.
- Prefer explicit, readable code over clever one-liners.

## Typing and API contracts

- Public functions, public methods, ports, DTOs, and application/domain boundary types **must** have explicit type annotations, including return types.
- Prefer domain/application types in core APIs; keep transport schemas, ORM models, and framework request/response types inside adapters.
- When the application layer needs command, query, or result objects, define them under the owning slice's `application/dtos/` and name them by intent (for example `CreateInvoiceCommand`, `ListInvoicesQuery`, `CreateInvoiceResult`).
- Port signatures may use domain types directly when they are the natural business boundary; otherwise prefer application DTOs from the owning slice's `application/dtos/` over transport or framework types.
- Avoid `Any`; use it only at narrowly contained boundaries to untyped third-party code. Document the reason when it persists beyond a thin shim.
- Prefer standard-library typing constructs supported by the project's minimum Python version (for example `Protocol`, `TypedDict`, `Literal`, `Self`, `TypeAlias`, and `collections.abc` generics).
- Use `typing_extensions` only when the project's minimum Python version does not yet provide the required construct.

## Python-specific defaults

- Prefer modern type annotation syntax supported by the project's minimum Python version.
- Use `None` only for a legitimate, documented absence value, never as a hidden error signal.
- Prefer timezone-aware `datetime` values for persisted or cross-process timestamps.
- Prefer explicit UTC sources such as `datetime.now(timezone.utc)` when recording interoperable timestamps.
- Prefer `pathlib.Path` for filesystem paths unless a library API requires `str`.
- Use context managers for files, connections, locks, and similar resources.
- Prefer `Enum`/`StrEnum` or `Literal` over magic strings for closed sets of values.
- Never use mutable default argument values; default to `None` and create the container inside the function.

## Boundary behavior (adapter input validation)

- Validate and normalize external inputs at **adapter boundaries** before calling application ports.
- Keep **mapping** between external schemas and application DTOs or other port-approved domain types inside adapters.
- For broader hexagonal boundary doctrine, see `003-architecture-guardrails.md`.
- For environment lookups, settings DTOs, config validation, and secret-handling mechanics, see `008-configuration-and-secrets.md`.

## Error handling

- Raise **layer-appropriate exceptions** (not generic `Exception`):
  - In `domain/` and `application/`: use domain/application-specific exceptions (typically from `domain/exceptions.py` or application exception modules).
  - In adapters: use adapter/infrastructure-specific exceptions internally when needed, then translate at adapter boundaries.
- **Never** use bare `except:`; catch the most specific exception possible.
- Preserve context with `raise CustomError(...) from err`.
- Validate inputs at module boundaries (e.g., adapters) and fail fast with clear errors.
- Avoid returning `None` for error states; raise unless the API explicitly allows it.
- In async code, do not swallow cancellation-related exceptions during cleanup; re-raise them after releasing resources.
- Translate exceptions at the **adapter boundary** into the caller's domain, such as a CLI or HTTP response, without leaking internal types.

## Logging

- Use the configured logger instead of `print()` in production code.
- Never log secrets, tokens, API keys, or other sensitive data.
- Keep logging setup centralized.
- Keep configuration and secret-source handling centralized according to `008-configuration-and-secrets.md`.
- For logger naming, structured context, log levels, and implementation mechanics, see `013-logging-conventions.md`.
