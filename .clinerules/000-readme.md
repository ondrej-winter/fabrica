# How this ruleset is structured

## Structure and ordering

- Files in `.clinerules/` are **active** rules.
- This ruleset is an **opinionated reusable profile** for Python projects using hexagonal architecture with vertical slices and Cline.
- Rule files use sortable three-digit prefixes (for example `000-`, `001-`, `002-`) to keep the reading order stable.
- Each file should focus on a single theme (core standards, architecture, testing, etc.).

## Opinionated defaults

- This ruleset is intentionally opinionated.
- Use `uv` for dependency management, environment management, and command execution.
- Use `ruff` for formatting, linting, and import cleanup.
- Use `ty` for type checking.
- Use `pytest` for automated tests.
- Use `pytest-asyncio` for async tests when async code is present.
- Use Google-style docstrings.
- Use `pyproject.toml` and `uv.lock` as the canonical tooling and dependency configuration surface.
- Prefer dependency groups for development-only tooling and test dependencies.
- Use the owning slice's `application/dtos/` as the default home for command, query, and result DTOs in the application layer.
- Follow hexagonal architecture with vertical feature slices, inward-pointing dependencies, and explicit ports/adapters boundaries.

## Rule precedence and conflict resolution

- Treat rules marked as **hard constraints** or **non-negotiable** as highest priority within `.clinerules/`.
- Explicit overrides beat implicit interpretation. When a later module intentionally sharpens an earlier rule, it should say so directly.
- More specific rules take precedence over broader rules on the same topic.
- **Must** statements take precedence over **Should** statements.
- If two rules with the same strength and scope still conflict, use file order only as a **last-resort tiebreaker**, then update the ruleset to make precedence explicit.
- Any intentional deviation must be documented in ADR/PR notes.

## Reusable-asset portability

- Keep this ruleset copyable into another repository without assuming a specific local folder workflow beyond `.clinerules/` itself.
- Do not require repository-specific maintenance conventions such as sibling "bank," "disabled," or archive folders inside reusable rule content.
- If a host repository wants local enable/disable mechanics, document them in repo-specific maintainer docs rather than in the reusable rules themselves.

## Adding or updating rules

- Prefer **small, focused** rule files rather than large monoliths.
- Use **Must/Should** language for clarity and consistency.
- When adding a new module, update this README and keep the sortable prefix order obvious and stable.

## Rule authoring standards

- Keep each module focused on one primary topic with a clearly implied owner.
- Avoid restating requirements owned by another module unless the later module is adding stricter or more specific constraints.
- Prefer one requirement per bullet so review discussions can reference a single rule precisely.
- Use **Must** only for review-blocking requirements.
- Use **Should** for strong defaults that may allow justified exceptions.
- When step-by-step guidance already exists in a skill, keep the rule focused on policy and reference the skill by name.
- When a later module intentionally overrides or sharpens an earlier rule, make that override explicit.

## Ownership and specialization

- Earlier files should define broad policy and defaults for their topic.
- Later specialized files should define detailed mechanics for narrower subtopics.
- When a specialized file exists, earlier files should point to it instead of repeating detailed guidance.
- Use skills for reusable procedures instead of embedding that guidance in rule files.

### Topic ownership map

- `001-cline-operating-guidance.md`: lightweight Cline operating behavior, scope control, and validation discipline shared across rulesets
- `002-core-standards.md`: universal coding behavior, typing defaults, DTO boundary guidance, error handling, and baseline logging policy
- `003-architecture-guardrails.md`: vertical-slice architecture boundaries, dependency direction, and ports/adapters responsibilities
- `004-testing-standards.md`: automated testing expectations; detailed pytest mechanics belong in `write-pytest-tests`
- `005-docs-and-adr.md`: required project documentation outside source code; concrete update workflow belongs in `update-project-docs`
- `006-module-structure.md`: file, package, feature-slice, and export mechanics; restructuring workflow belongs in `split-python-module`
- `007-performance-and-observability.md`: performance expectations and runtime visibility; concrete instrumentation workflow belongs in `add-observability`
- `008-configuration-and-secrets.md`: runtime configuration sources, settings DTO boundaries, and secret safety
- `009-repo-navigation.md`: project discovery, canonical vertical-slice layout, and navigation principles; command recipes belong in `workflows/update-repo-navigation.md`
- `010-pr-and-commit-hygiene.md`: review and change-management discipline
- `011-tooling-and-ci.md`: dependency-group, local quality gate, and CI policy; command sequencing belongs in quality-gate skills
- `012-documentation-standards.md`: in-code documentation policy; drafting mechanics belong in `write-python-docstrings`
- `013-logging-conventions.md`: logging implementation mechanics and privacy-safe logging details
- `999-command-execution-safety.md`: atomic command execution and process safety rule shared across rulesets

## Active modules

- `001-cline-operating-guidance.md` - Read before editing, make minimal changes, validate proportionally, and avoid unrelated churn
- `002-core-standards.md` - Naming, formatting, typing defaults, DTO guidance, error handling, baseline logging policy
- `003-architecture-guardrails.md` - Hexagonal vertical-slice architecture doctrine, ports/adapters boundaries, adapter directory structure
- `004-testing-standards.md` - Testing pyramid, isolation requirements, and review-blocking testing policy
- `005-docs-and-adr.md` - Documentation obligations, ADR triggers, and changelog policy
- `006-module-structure.md` - File organization, splitting rules, and `__init__.py` conventions
- `007-performance-and-observability.md` - Performance, tracing, metrics, and observability policy
- `008-configuration-and-secrets.md` - Configuration source ownership, settings DTOs, validation, and secret safety
- `009-repo-navigation.md` - Generic navigation guidelines for hexagonal vertical-slice architecture, including canonical application and test layout
- `010-pr-and-commit-hygiene.md` - PR size, commit messages, reviews
- `011-tooling-and-ci.md` - `uv` dependency-group, validation policy, and CI expectations
- `012-documentation-standards.md` - Clear, concise docstrings and comments policy
- `013-logging-conventions.md` - Module-level logger standard, structured context, and safe redaction practices
- `999-command-execution-safety.md` - Hard ban on inline interpreter heredocs; require file-based helper scripts and non-interactive version-control usage

## Workflows

- `workflows/update-repo-navigation.md` - Generate project-specific navigation maps when adapting this reusable ruleset to a concrete project
- `workflows/improve.md` - Focused improvement workflow included here for drop-in portability

## Related skills

Skills should own focused procedures.

- When one skill needs a neighboring task, reference the related skill by name
  and decision context instead of repeating the full procedure.
- Keep references portable and optional unless a dependency is truly mandatory.
- Prefer short inline references inside the relevant step.
- Add a dedicated `Related skills` section only when a skill has several common
  handoffs that would otherwise be hard to discover.

### Skill index

- `bootstrap-python-app` - Initialize a new Python hexagonal vertical-slice project with base tooling and structure
- `add-hexagonal-feature` - Add an end-to-end vertical feature slice across domain, application, adapters when needed, and tests
- `python-add-port` - Define a focused inbound or outbound port contract in the owning slice's application layer
- `python-add-adapter` - Implement an inbound or outbound adapter against an existing slice-owned port
- `python-add-env-settings-adapter` - Add an environment-backed runtime settings adapter with configuration-slice-owned settings DTOs and adapter-owned parsing/validation
- `update-project-docs` - Update README, changelog-style notes, and related project-facing docs after a change
- `split-python-module` - Safely split a large Python module or package while preserving boundaries and intentional imports
- `add-observability` - Add profiling, metrics, tracing, and operational notes for meaningful workflows
- `write-python-docstrings` - Write concise Google-style docstrings and inline comments where they add value
- `write-adr` - Record significant architectural decisions and consequences
- `format-python-code` - Formats Python code using ruff and applies safe auto-fixes
- `lint-python-code` - Lints Python code using ruff and ty for type checking
- `write-pytest-tests` - Writes or refactors Python tests in clear, pytest-native style
- `run-python-tests` - Runs automated tests for a Python project using pytest
- `run-local-quality-gate` - Orchestrates the execution of Python code formatting, linting, type checking, and testing

### Delegation principles

- Use the most specific skill that owns the current procedure.
- Use `add-hexagonal-feature` for end-to-end vertical-slice use case work; hand off to
  `python-add-port`, `python-add-adapter`, or `python-add-env-settings-adapter`
  for focused boundary and adapter procedures.
- Use `write-pytest-tests`, `run-python-tests`, and `run-local-quality-gate` for
  test creation and validation workflows.
- Use `update-project-docs`, `write-python-docstrings`, and `write-adr` when a
  change affects user-facing docs, public code contracts, or durable
  architectural decisions.
- Keep detailed handoff rules inside the owning skill instead of duplicating
  full workflows in this README.

## Enforcement and automation matrix

Use this map to keep "Must" rules enforceable rather than merely advisory.

Interpret enforcement labels as follows:

- **Tool-enforced**: verified directly by automated tooling.
- **Review-enforced**: verified primarily in code review.
- **Process-enforced**: verified through operating discipline when tools cannot reliably enforce the rule.

| Rule area                                           | Primary enforcement                                                                | Secondary enforcement                        |
| --------------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------- |
| Naming, formatting, imports                         | `uv run ruff check . --fix`, `uv run ruff format .`, `uv run ruff check .`         | PR review                                    |
| Type contracts and API drift                        | `uv run ty check .`                                                                | PR review                                    |
| Behavior changes and regressions                    | `uv run pytest`                                                                    | Targeted regression and contract tests       |
| Architecture boundaries (hexagonal vertical slices) | Review-enforced against `003-architecture-guardrails.md`                           | Optional import-lint/custom boundary scripts |
| Module/file structure conventions                   | Review-enforced against `006-module-structure.md`                                  | Optional project audit script                |
| Configuration and secrets                           | Review-enforced against `008-configuration-and-secrets.md`                         | Startup validation and focused config tests  |
| Docs/ADR/changelog updates                          | Review-enforced via PR checklist                                                   | Release checklist                            |
| Logging conventions                                 | Review-enforced against `013-logging-conventions.md`                               | Runtime log sampling                         |
| Command execution safety                            | Process-enforced (no `python - <<'PY'` patterns; git `--no-pager`/non-interactive) | PR review                                    |

## Rules-to-enforcement alignment

- Hard constraints should be backed by tool enforcement where practical; otherwise, mark them as review-enforced or process-enforced.
- If automation cannot fully enforce a rule, write the rule so a reviewer can still evaluate compliance consistently.
- Keep rule text, examples, and tooling configuration aligned. When they differ intentionally, document the reason in the relevant rule file or PR notes.

## Scope

These rules apply to Python projects using hexagonal architecture with vertical slices unless explicitly stated otherwise.

## Project-specific customization

For project-specific navigation and structure details:

1. Use the workflow in `workflows/update-repo-navigation.md` to generate a current map, or follow the same steps manually if the workflow file is not bundled.
2. Store project-specific documentation in `docs/` or the project root.
3. Keep `.clinerules/` generic and portable across projects.
