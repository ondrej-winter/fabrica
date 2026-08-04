---
name: documentation-and-adrs
description: Decide whether durable documentation is needed, choose the right documentation artifact, and route ADR or project documentation work to the appropriate specialized skill.
metadata:
  version: "1.2.3"
  dependencies:
    tools: []
    skills:
      - name: write-adr
        purpose: Record durable architectural, product, data, security, or workflow decisions when an ADR is warranted.
        required: false
      - name: update-project-docs
        purpose: Update project-facing documentation after visible behavior, configuration, operation, or workflow changes.
        required: false
---

# Documentation and ADRs

Use this skill when you need to decide what durable documentation, if any, a
change needs. This is a routing and judgment skill. It helps identify the reader,
purpose, and best documentation surface, then delegates detailed writing mechanics
to narrower skills when they apply.

Good documentation explains intent, constraints, trade-offs, and consequences. It
does not restate obvious code or create stale process noise.

## When to use this skill

Use this skill when:

- making an architectural, product, data, security, or workflow decision
- changing public or compatibility-sensitive interfaces
- shipping behavior that users, operators, or maintainers need to understand
- recording migration, deployment, rollback, or troubleshooting guidance
- updating project commands, setup, conventions, or agent instructions
- repeatedly explaining the same design or gotcha

Do not use this skill for throwaway prototypes, obvious comments, or documentation
that has no likely reader or maintenance owner.

Use a specialized skill directly when the needed artifact is already clear:

- Use `write-adr` when the main task is creating, superseding, numbering, naming,
  or indexing an architecture decision record.
- Use `update-project-docs` when the main task is updating README, changelog,
  usage, configuration, migration, operational, or troubleshooting documentation.

## Steps

### 1. Identify the reader and purpose

Before writing, state:

- who needs the documentation
- what task or decision it supports
- what the reader already knows
- what can go wrong without the documentation
- where the documentation should live

Choose the smallest durable format that fits the need.

### 2. Choose the documentation artifact

Common types include:

- README or quick-start guide for project setup and common commands
- architecture decision record for significant decisions and trade-offs
- interface documentation for public APIs, commands, events, schemas, or modules
- runbook for operational procedures and incident recovery
- migration guide for moving from one behavior to another
- changelog or release note for shipped user-visible changes
- agent-facing rules or context for project conventions and constraints

Prefer the existing canonical documentation surface over creating a duplicate.
If no durable reader or maintenance owner exists, skip the documentation change
and explain why.

### 3. Route to specialized skills

Use the narrowest skill that owns the concrete mechanics:

- For durable architectural, product, data, security, or workflow decisions, use
  `write-adr`.
- For reader-facing project documentation updates, use `update-project-docs`.
- For public or cross-boundary interfaces, document the interface contract in the
  project’s preferred API, schema, command, event, or module documentation.
- For operational procedures, create or update the runbook, alert response,
  dashboard note, rollback guidance, or troubleshooting guide readers already use.
- For source-level explanations, add comments or docstrings only where they
  explain non-obvious intent, constraints, invariants, or hazards.

Do not delete old ADRs. If a decision changes, write a new ADR that supersedes or
deprecates the old one.

When routing to a specialized skill, read that skill's `SKILL.md` before editing
so its format, naming, validation, and handoff requirements govern the concrete
documentation change.

### 4. Check cross-document consistency

Some changes need more than one artifact. Check whether the change affects:

- architectural rationale or decision history
- README or quick-start instructions
- public interface docs
- configuration reference or examples
- migration, deprecation, rollback, or compatibility notes
- changelog or release notes
- runbooks, alerts, dashboards, or troubleshooting guides
- agent rules, conventions, or repository navigation docs

When multiple artifacts are needed, keep each one focused. Put rationale in ADRs,
usage in project docs, contracts in interface docs, and procedures in runbooks.

### 5. Document interfaces by contract

For public or cross-boundary interfaces, document:

- purpose and supported use cases
- inputs, outputs, side effects, and error behavior
- compatibility expectations
- examples that are minimal and portable
- validation, authentication, authorization, or operational constraints when
  relevant

Use the project’s preferred contract format, such as schema files, reference docs,
types, command help, examples, or generated documentation.

### 6. Comment intent, not obvious mechanics

Inline comments should explain non-obvious intent, constraints, or hazards.

Good comments answer:

- why this approach is necessary
- what invariant must be preserved
- what external constraint shaped the code
- what future maintainer should not simplify away

Avoid comments that restate syntax, preserve deleted code, or create TODOs with
no owner or timeframe.

### 7. Validate and prune

Before handoff:

- remove commented-out code and obsolete docs
- check links and referenced file names when practical
- confirm examples match current behavior
- keep docs concise enough to be maintained
- record validation evidence or skipped validation

## Red flags

- significant decision has no rationale
- docs explain what code already says but omit why
- public interface lacks contract, examples, or compatibility notes
- setup docs contain unverified commands or stale prerequisites
- TODO comments have no owner or follow-up path
- old decisions are deleted instead of superseded
- docs are updated separately from the behavior they describe

## Output checklist

- reader and purpose are explicit
- documentation type fits the need
- specialized ADR work is routed to `write-adr` when needed
- project-facing documentation work is routed to `update-project-docs` when needed
- interface docs describe contract and compatibility when relevant
- inline comments explain intent rather than obvious mechanics
- setup or workflow commands are verified or marked as examples when included
- stale docs and commented-out code are removed
- validation evidence is documented before handoff
