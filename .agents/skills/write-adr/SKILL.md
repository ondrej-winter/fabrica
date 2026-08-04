---
name: write-adr
description: Create an Architecture Decision Record with the next sequential number, a clear title, and documented consequences when asked to record an architectural decision.
metadata:
  version: "1.1.5"
  dependencies:
    tools: []
    skills:
      - name: documentation-and-adrs
        purpose: Decide whether an ADR is the right documentation artifact for the change.
        required: false
      - name: update-project-docs
        purpose: Update related project-facing documentation after recording the decision.
        required: false
---

# Write an Architecture Decision Record (ADR)

Use this skill when the user asks to document an architectural decision, record
a design choice, or create an ADR. ADRs are for durable decisions, not routine
implementation notes.

Use `documentation-and-adrs` first when it is unclear whether the change needs an
ADR, project documentation, interface documentation, a runbook, or no durable
documentation. Use `update-project-docs` as well when the decision changes
reader-facing behavior, configuration, operations, or workflows.

## Goal

Create a new ADR in the ADR directory with the next sequential number, a clear
title, and a concise record of the decision and its consequences.

## Steps

### 1. Locate the ADR directory

Use the repository's existing ADR directory when one is present. Common names
include `adr/` and `docs/adr/`.

If no ADR directory exists, ask for the preferred location when that choice is
unclear. Create a new ADR directory only when the user provides a location or the
repository has an existing documentation convention that makes the location
obvious.

### 2. Determine the next ADR number

Inspect Markdown files in the ADR directory, identify the existing numeric prefix
width and file-name separator, find the highest prefix, then increment it by one
while preserving that convention.

- If no ADRs exist yet, start with `0001` and use a hyphen after the number.
- Example: if `0003-...` is the latest ADR, use `0004`.
- Ignore files that do not follow the directory's numeric ADR naming convention.

### 3. Create the ADR file

Use the repository's existing ADR file-name convention. If no convention exists,
use this format:

`<adr_directory>/<NNNN>-<short-title-kebab-case>.md`

Example:

`<adr_directory>/0004-standardize-api-error-format.md`

Derive the slug from the ADR title by converting it to kebab-case. Remove filler
words only when doing so keeps the title recognizable.

Before writing, confirm that the selected number and path do not already exist.

### 4. Fill in the ADR template

If the repository already has an ADR template or consistent ADR format, follow
that local style and adapt the fields below rather than replacing it.

Use today's date for the Date field unless the user requests a different date.

```markdown
# <NNNN>. <Short Title in Title Case>

Date: <YYYY-MM-DD>
Status: Proposed | Accepted | Deprecated | Superseded by [NNNN](./<NNNN>-<slug>.md)

## Context

Describe the situation, constraints, and trade-offs that make this decision
necessary.

## Decision

State the decision clearly in one or two sentences. Prefer active voice, for
example: "We will use X because Y."

## Consequences

List the consequences. Use subsections such as Positive, Negative, and Neutral
when helpful. For simple decisions, a flat list is fine.

- ...

## Alternatives considered

Include this section when meaningful alternatives were evaluated. Omit it when
the decision follows an obvious convention or has no real alternatives.

| Option | Reason rejected |
| ------ | --------------- |
| ...    | ...             |
```

### 5. Set the status

Choose the status that matches the user's intent:

| Status                                     | Use when                                                  |
| ------------------------------------------ | --------------------------------------------------------- |
| `Proposed`                                 | The decision is still under discussion.                   |
| `Accepted`                                 | The decision has been agreed and is in effect.            |
| `Deprecated`                               | The decision was once accepted but is no longer followed. |
| `Superseded by [NNNN](./<NNNN>-<slug>.md)` | A newer ADR replaces it.                                  |

If the user does not specify a status, default to `Proposed`. Use `Accepted`
only when the user clearly indicates that the decision is already in effect.

### 6. Update or create the ADR index

If the ADR directory already contains an index file such as `README.md` or
`index.md`, update it.

- If it already contains an ADR table, append an entry such as:

```markdown
| [<NNNN>](./<NNNN>-<slug>.md) | <Short Title> | <Date> | <Status> |
```

- If an index file exists but does not yet contain an ADR table, add one.
- If no ADR index file exists, create one such as `README.md` with a header
  like:

```markdown
# Architecture Decision Records

| ADR                          | Title         | Date   | Status   |
| ---------------------------- | ------------- | ------ | -------- |
| [<NNNN>](./<NNNN>-<slug>.md) | <Short Title> | <Date> | <Status> |
```

### 7. Review and hand off

Before finishing, review the ADR and any index update for:

- the expected sequential number and file name
- a clear decision statement
- consequences that describe meaningful trade-offs
- valid relative links to related ADRs, issues, or supporting documents
- consistency with the repository's existing ADR style

In the handoff, report the ADR path, status, and any documentation updates made
alongside it.

## Good ADR practices

- Focus on why and what was decided, not step-by-step implementation details.
- Keep the context factual and specific.
- Record one decision per ADR.
- Keep the decision statement short and explicit.
- Link related ADRs, issues, or PRs when helpful.
- Preserve existing ADR style when the repository already has a clear template.
- Do not delete old ADRs; deprecate or supersede them.
