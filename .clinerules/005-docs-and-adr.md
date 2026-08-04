# Documentation rules: README updates, ADRs, changelog notes, API docs

Use these rules to keep documentation consistent and architectural decisions traceable.
Use the `update-project-docs` skill when you need a practical checklist for
README, changelog-style notes, or related project-facing documentation updates.

## README updates

- **Must** update `README.md` when behavior, configuration, or usage changes.
- **Should** add short usage examples when new CLI flags or commands are introduced.
- **Must** document new environment variables and defaults.
- **Must** link from the main README to the canonical settings reference under `docs/` when the project has an explicit runtime settings model.
- **Must** maintain `.env.example` with every supported environment variable and safe example values when environment-backed configuration exists.
- **Should** document supported Python version(s), the `uv` workflow (`uv sync`, `uv run ...`), and the local quality gate commands when they are project-relevant.
- In-code docstring and comment standards are covered in `012-documentation-standards.md`.

## Configuration references

- **Must** maintain a dedicated settings reference under `docs/` when a runtime settings model exists.
- **Must** list every settings model option with its environment variable name, field name, type or format, required/default behavior, safe example value, secret/redaction status, and runtime usage.
- **Must** keep configuration docs, `.env.example`, settings model fields, and tests synchronized.
- **Should** keep README configuration content brief and link to the dedicated reference instead of duplicating full settings tables.

## ADRs (Architecture Decision Records)

- **Must** create an ADR when a decision materially affects architecture, dependencies, or boundaries.
- When an ADR is needed, use the `write-adr` skill for the creation process, numbering, naming, and template.
- Put architectural rationale in ADRs rather than module docstrings or inline comments.

## Changelog notes

- **Must** call out breaking changes explicitly.
- **Must** record release-facing changes in `CHANGELOG.md` when that file exists.
- **Should** include a concise changelog-style summary in PR notes when `CHANGELOG.md` is not maintained.

## API docs rules

- **Should** document public ports, CLI interfaces, and plugin extension points.
- **Must** keep DTO field meanings aligned with domain terminology.
- **Should** document caller-visible error semantics, idempotency and retry expectations, and pagination or streaming behavior for external interfaces when relevant.
