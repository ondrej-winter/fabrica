# Specification: [Project or Feature Name]

## Status

- State: Draft
- Accepted by: Not applicable until accepted
- Accepted on: Not applicable until accepted
- Revision: [Optional revision identifier.]
- Supersedes: Not applicable

## Objective

[Describe what is being built, for whom, and why it matters.]

## Current Context

[Describe relevant existing behavior, files, systems, workflows, constraints,
and dependencies.]

## Assumptions

- [State an unconfirmed belief that affects requirements or implementation, and
  explain how it will be confirmed or tested.]

## Desired Behavior

[Define the required functional, operational, data, interface, or workflow
behavior. Include observable outcomes and important failure behavior.]

## Scope

### In Scope

- [Required capability, affected workflow, or deliverable.]

### Out of Scope

- [Related behavior or work intentionally excluded from this specification.]

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Build | `<confirmed_build_command>` | Required |
| Tests | `<confirmed_test_command>` | Required |
| Lint or static analysis | `<confirmed_lint_or_check_command>` | Required |
| Documentation | `<confirmed_docs_command>` | [Required, unknown, or not applicable.] |
| Migration or compatibility | `<confirmed_migration_command>` | [Required, unknown, or not applicable.] |
| Manual acceptance | [Describe the manual check.] | [Required or not applicable.] |

Use `Not applicable` when a validation category genuinely does not apply. Keep an
unknown command visible as an open question rather than inventing one.

## Project Structure

- Specification: `docs/specs/<name>-spec.md`
- `<source_location>`: [Implementation responsibility.]
- `<test_location>`: [Test responsibility.]
- `<docs_location>`: [Documentation responsibility.]

## Conventions and Constraints

[Describe relevant naming, formatting, error-handling, logging, API,
accessibility, security, privacy, compatibility, platform, or operational
requirements. Mark individual concerns as not applicable only when supported by
project evidence or user confirmation.]

## Testing Strategy

[Describe the test levels, fixtures, edge cases, failure cases, and acceptance
checks that will demonstrate conformance with this specification.]

## Execution Boundaries

- Always: [Required practices or invariants.]
- Ask first: [Scope-expanding, destructive, costly, or risky actions.]
- Never: [Explicitly prohibited behavior or changes.]

## Success Criteria

- [State a specific, observable, and verifiable outcome.]

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| [Unresolved decision.] | [Affected requirement or workflow.] | Yes or No | [Person, role, or evidence source.] | Unresolved |
