# Testing Patterns

Use these patterns when choosing how to make behavior verifiable before or during implementation.

Consult this reference when the main TDD cycle is clear but the test shape is not.
Choose the narrowest pattern that proves the behavior, then record the focused
test command and any broader validation that should run before handoff.

## Behavior-first tests

- Name the behavior from the user's or caller's perspective.
- Arrange only the state required for that behavior.
- Assert the observable outcome rather than internal implementation details.
- Keep setup small enough that the failure points to one behavior.

## Regression tests

- Reproduce the reported failure before fixing it.
- Keep the test focused on the bug's public symptom.
- Verify the test fails for the current behavior and passes after the fix.
- Add edge cases only when they represent distinct risks.

## Contract tests

- Use contract tests at module, service, adapter, or API boundaries.
- Verify success, failure, and malformed input paths.
- Avoid coupling the contract test to a single implementation when alternatives are allowed.

## Anti-patterns

- Testing private implementation details instead of behavior.
- Writing broad tests with many unrelated assertions.
- Adding mocks that duplicate the implementation.
- Accepting a test that never failed for the bug or feature it claims to cover.

## Handoff readiness

- The test failed before the implementation change when the work changed behavior.
- The passing test proves the public behavior, contract, or regression symptom.
- The chosen scope is documented when it is broader than a unit test.
- Focused and broader validation commands are reported in the handoff.
