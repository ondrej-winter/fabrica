---
name: update-repo-navigation
description: Create or refresh concise repository navigation guidance when agent instructions, source layout, tests, commands, or canonical documentation locations have changed.
metadata:
  version: "1.0.0"
  dependencies:
    tools:
      - name: filesystem-search
        purpose: Inspect repository directories, configuration, task definitions, and documentation without modifying generated artifacts.
        required: true
    skills:
      - name: context-engineering
        purpose: Keep repository discovery focused on durable, high-signal context.
        required: false
      - name: update-project-docs
        purpose: Apply focused updates to an existing repository navigation document.
        required: false
---

# Update Repository Navigation

Use this skill when a repository's agent-facing navigation guide is missing,
generic, stale, or inconsistent with the actual source, tests, tooling, and
documentation layout.

The result should help an agent find the right files quickly. It should not copy
the entire directory tree or duplicate detailed architecture and workflow
documentation.

## Steps

### 1. Identify the canonical navigation surface

Prefer the repository's existing agent instruction file, such as `AGENTS.md`, or
its documented equivalent. Do not create a second navigation guide when an
existing canonical file can be updated.

### 2. Inspect the real repository structure

Read package and tool configuration, then inspect directories at a bounded depth.
Identify:

- source/package roots
- feature, layer, or component ownership boundaries
- composition and entry points
- unit, integration, contract, and end-to-end test locations
- canonical specifications, ADRs, guides, and generated documentation sources
- task definitions and CI configuration
- skill, plugin, extension, or automation locations

Ignore caches, virtual environments, build output, generated reports, and other
transient directories unless agents must handle them specially.

### 3. Verify architecture and ownership

Use imports, configuration, nearby examples, and architecture checks to confirm
what each important directory owns. Do not infer responsibility from names alone.

Call out intentional exceptions, such as shared adapters or composition modules,
when their ownership would otherwise be surprising.

### 4. Record canonical commands

Discover setup, focused validation, full quality-gate, build, and opt-in test
commands from repository instructions, task files, package configuration, and CI.

Prefer aggregate project commands when available. Distinguish default offline
checks from live, destructive, privileged, or credential-dependent workflows.

### 5. Write a compact map

Update the canonical navigation surface with:

- a short repository summary
- important directories and their responsibilities
- where to start for common changes
- authoritative validation commands
- links or paths to specifications and decisions that govern behavior

Keep the map concrete and repository-specific. Avoid generic placeholder trees,
exhaustive file inventories, and step-by-step implementation procedures that
belong in task skills.

### 6. Check for stale references

Search for renamed directories, removed workflow files, obsolete commands, and
duplicate navigation guidance. Update or remove stale references rather than
leaving conflicting instructions.

### 7. Validate and hand off

Confirm every documented path exists and every command matches the repository's
current configuration. Run configured Markdown or documentation checks when
available.

Report the navigation file changed, important corrections made, and validation
performed.

## Output checklist

- navigation describes the real repository rather than a generic template
- source, tests, composition, docs, and tooling locations are covered
- directory responsibilities were verified from content or configuration
- default and opt-in commands are clearly distinguished
- stale paths and duplicate guidance were removed
- the canonical agent instruction surface remains concise and authoritative
