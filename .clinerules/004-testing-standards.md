# Testing standards: pyramid, pytest conventions, fixtures, mocks, coverage

Use these rules for all automated tests to keep signal high and feedback fast.

For test directory structure and organization, see `009-repo-navigation.md`.
Use the `write-pytest-tests` skill when you need concrete pytest-native
mechanics, test-double patterns, or example test structures.

## Test pyramid expectations

- **Must** keep the majority of tests as unit tests (fast, isolated, no I/O).
- **Should** use integration tests sparingly for adapter boundaries that touch real I/O.
- **Should** add contract tests around important ports/adapters when multiple implementations must honor the same behavior.
- **Must** avoid mixing adapter behavior into domain unit tests.

## Test quality defaults

- **Must** keep tests deterministic and isolated; avoid hidden reliance on wall clock time, randomness, ambient environment variables, or test order.
- **Should** control time, randomness, filesystem, and network behavior explicitly through fixtures, fakes, or test helpers.
- **Should** prefer small builders/factories over large shared fixtures when setup starts hiding the behavior under test.
- **Should** place tests in directories that mirror slice ownership and source responsibility, such as `tests/unit/features/<feature_name>/domain/`, `tests/unit/features/<feature_name>/application/`, and `tests/unit/features/<feature_name>/adapters/inbound/`.
- **Must not** rely on live external services in the default local or CI suites.

## Pytest conventions

- **Must** use `pytest` as the default test framework.
- **Must not** introduce new `unittest.TestCase`-based tests.
- **Must** name tests `test_<behavior>()` with clear behavior-oriented names.
- **Must** keep assertions focused on observable outcomes, not implementation details.
- **Should** prefer pytest-native assertions and helpers over `unittest`-style setup and assertions.
- Use the `write-pytest-tests` skill when adding or refactoring tests and
  detailed pytest-native mechanics are needed.
- Legacy `unittest` tests may be migrated opportunistically, but **should not** be expanded in new work.

## Mocks, stubs, and fakes

- **Must** isolate outbound ports in application tests with mocks, fakes, or stubs so orchestration stays deterministic.
- **Must** avoid mocking domain entities or value objects.
- **Should** prefer hand-written fakes or thin test doubles over broad `MagicMock`
  usage and deep mock chains that mirror implementation details.
- **Should** use shared contract tests when multiple adapters implement the same important port.

## Async and boundary testing

- **Should** use `pytest-asyncio` consistently when testing async code.
- **Must** isolate real network, filesystem, and database access to explicit integration/e2e tests.
- **Should** use temporary directories, ephemeral databases, or sandbox resources instead of shared developer state.

## Coverage and regression expectations

- **Must** add or update tests when behavior changes.
- **Should** add regression tests for bugs before fixing them.
- **Should** add property-based tests (for example with Hypothesis) or edge-case matrix tests when domain invariants or parser/serializer boundaries have a broad input space.
- **Should** keep coverage stable or improving; document intentional gaps in PR notes.

## Running tests

- Use the `run-python-tests` skill for focused and full-suite execution.
- Use the `run-local-quality-gate` skill before handoff or a PR.
