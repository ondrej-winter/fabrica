---
name: update-project-docs
description: Update project-facing documentation after a reader-visible behavior, configuration, operation, or developer workflow change.
metadata:
  version: "1.2.2"
  dependencies:
    tools: []
    skills:
      - name: documentation-and-adrs
        purpose: Decide whether a change needs an ADR, project documentation, interface documentation, runbook, or no durable documentation.
        required: false
      - name: write-adr
        purpose: Record durable architectural, product, data, security, or workflow decisions when documentation updates require an ADR.
        required: false
---

# Update Project Docs

Use this skill when a change affects reader-visible behavior, configuration,
operations, or developer workflows and project-facing documentation must stay in
sync.

Use `documentation-and-adrs` first when it is unclear whether the change needs an
ADR, project documentation, interface documentation, a runbook, or no durable
documentation. Use `write-adr` as well when the change records a durable
architectural, product, data, security, or workflow decision.

## When to use this skill

Use this skill when you need to update:

- the main project README
- release-facing notes such as a changelog
- operator, contributor, or troubleshooting docs
- usage examples for new commands, flags, APIs, workflows, or configuration

Use `write-adr` instead when the main task is recording a durable architectural
decision rather than updating usage or operational documentation.

## Steps

### 1. Identify the reader-visible change

List what changed from a reader's perspective, for example:

- a new command, option, endpoint, feature, or workflow
- a new setting, environment variable, or configuration default
- a changed setup step, dependency workflow, or compatibility requirement
- a new operational concern such as alerts, dashboards, or troubleshooting
- a breaking change, migration, deprecation, or rollback concern

If the change is not reader-visible, keep documentation updates minimal and
explain why no durable docs changed.

### 2. Find the right documentation surface

Inspect existing documentation before editing. Prefer updating the canonical
source that readers already use instead of creating duplicate explanations.
Match the existing documentation's terminology, heading style, link style, and
level of detail unless those conventions are inaccurate for the change.

If a documentation page is generated, synced, or derived from another file, edit
the source of truth instead of the generated target unless the project explicitly
requires a local exception.

Do not create a new documentation surface unless no existing canonical location
fits the change or the user specifically asks for a new artifact.

Common surfaces include:

- overview and quickstart documentation
- installation or setup instructions
- configuration reference
- API, command, or workflow examples
- operations, troubleshooting, or migration notes
- release notes or changelog entries

### 3. Update only affected sections

Make focused edits that preserve the existing structure and style.

- Keep wording concrete and action-oriented.
- Avoid broad rewrites unless the existing section is misleading.
- Remove or update stale instructions that conflict with the change.
- Keep examples short, accurate, and runnable when possible.

### 4. Document configuration changes explicitly

If the change introduces or modifies configuration, document:

- setting or variable name
- expected type or format
- default value or absence behavior
- where the setting is read or applied
- whether existing users need to change anything

### 5. Add operational notes when relevant

When the change affects operations, document practical details such as:

- new failure modes
- troubleshooting steps
- dashboard, alert, or log expectations
- rollout, migration, or rollback guidance
- compatibility or data-handling implications

### 6. Capture release-facing notes

If the project maintains release notes or a changelog, add or update the relevant
entry. If no durable release file exists, prepare a concise handoff note that
covers:

- what changed
- whether it is breaking
- what a user, operator, or maintainer needs to do

### 7. Validate the docs

Review the final documentation as a reader would.

- Confirm links, commands, names, and examples match the current code.
- Confirm the documentation does not overpromise behavior.
- Confirm architectural rationale is recorded in an ADR when needed.
- Run any available documentation checks if the project provides them.
- Report any skipped documentation updates and the reason they were not needed.
- Include the documentation files changed and validation performed in the
  handoff.

## Output checklist

- reader-visible change is documented in the right place
- stale instructions are updated or removed
- examples and configuration references are accurate
- release-facing note is captured when relevant
- operational or migration notes are included when needed
- generated or synced documentation was updated at its source of truth
