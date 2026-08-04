---
name: deprecation-and-migration
description: Plan and execute safe deprecations, migrations, replacements, and removals by measuring usage, supporting consumers, preserving compatibility, and verifying that old paths are no longer active.
metadata:
  version: "1.1.2"
  dependencies:
    tools: []
    skills: []
---

# Deprecation and Migration

Use this skill when replacing, retiring, consolidating, or removing a system,
interface, feature, dependency, workflow, configuration surface, or documented
behavior. The goal is to reduce long-term maintenance cost without surprising
active consumers or breaking compatibility-sensitive paths.

Deprecation is the decision and communication process. Migration is the work of
moving consumers safely from the old path to the new one. Removal happens only
after usage and risk have been verified.

## When to use this skill

Use this skill when:

- replacing an old implementation, API, library, adapter, workflow, or feature
- consolidating duplicate behavior
- removing dead or unowned code that may still have consumers
- migrating users, services, modules, data, configuration, or documentation
- deciding whether to maintain a legacy path or invest in removal
- designing a new interface and planning how it could be retired later

Do not use this skill to remove behavior just because it is inconvenient. First
verify ownership, usage, replacement readiness, and migration risk.

## Principles

- Code and operational surfaces carry maintenance cost. Remove what no longer
  earns its keep, but do it safely.
- Observable behavior becomes a contract when consumers depend on it, even if it
  was undocumented.
- Deprecation without a usable replacement is usually abandonment, not migration.
- Consumers need clear timelines, compatibility notes, tooling, and support.
- Removal is complete only when code, tests, docs, configuration, monitoring, and
  references are cleaned up.

## Steps

### 1. Decide whether deprecation is justified

Answer:

- What unique value does the old path still provide?
- Who or what consumes it?
- What observable behavior do consumers rely on?
- What replacement exists, and is it ready?
- What is the migration cost for each consumer group?
- What is the cost or risk of keeping the old path?
- What happens if migration is delayed?

If active consumers remain and no replacement exists, build or identify the
replacement before announcing removal.

### 2. Measure usage and ownership

Do not rely on guesses. Gather evidence from available sources such as metrics,
logs, dependency analysis, repository search, configuration, support tickets,
runtime traces, docs, and owner interviews.

Record:

- active consumers and owners
- removal owner and decision maker
- known undocumented dependencies
- usage volume and criticality
- compatibility-sensitive behaviors
- data, configuration, or integration points affected
- unknowns that require follow-up

### 3. Choose advisory or compulsory deprecation

Use advisory deprecation when migration is optional or the old path can remain
stable for a while. Use compulsory deprecation only when risk, cost, security,
compliance, or blocking complexity justifies a deadline.

For compulsory deprecation, provide:

- deadline and rationale
- working replacement
- migration guide
- support path
- verification method
- exception process when needed

### 4. Prepare the replacement and migration path

Before broad announcement, confirm the replacement:

- covers critical use cases
- has parity or intentionally documented differences and compatibility limits
- is validated in representative environments
- has rollback or fallback guidance when applicable
- exposes enough observability to compare old and new behavior and prove usage
  decline on the old path
- includes migration tooling or examples when migration is repetitive

Use incremental migration patterns when risk is high, such as parallel run,
adapter, compatibility shim, feature flag, canary, staged rollout, or staged
consumer migration.

### 5. Announce and document

Write a concise notice:

```md
## Deprecation notice: <old_surface>

Status: <advisory or compulsory>
Replacement: <new_surface>
Reason: <why this is changing>
Removal owner: <owner or decision maker>
Migration deadline: <date or none>
Affected consumers: <known scope>
Removal criteria: <evidence required before removal>
Migration steps:

1. <step>
2. <step>

Verification: <how to prove migration worked>
Support or escalation: <contact or process>
```

Keep the notice close to the old surface and in durable project documentation.

### 6. Migrate incrementally

For each consumer:

1. Identify old-path touchpoints.
2. Move to the replacement.
3. Verify behavior and compatibility.
4. Remove references to the old path.
5. Record completion or remaining risk.

If you own the deprecated surface, prefer helping or automating consumer migration
over leaving consumers to infer the work.

### 7. Remove only after zero active usage

Before removal, verify:

- no active consumers remain
- fallback or rollback expectations are clear
- replacement behavior is stable under representative usage
- alerts, dashboards, docs, examples, generated files, and configuration no
  longer reference the old path
- tests cover the replacement and no longer depend on the old behavior
- stakeholders accept the removal timing

Then remove code, tests, docs, configuration, feature flags, compatibility shims,
and notices that have served their purpose.

## Red flags

- removal announced without usage measurement
- no working replacement or migration guide
- active consumers with no owner or support path
- deprecated path keeps receiving new features
- advisory deprecation remains unresolved indefinitely
- compatibility behavior changed without notice
- old path removed before metrics, logs, or dependency checks show zero usage
- documentation and configuration still reference removed behavior

## Output checklist

- deprecation rationale and scope are explicit
- active usage and ownership were measured
- removal owner and decision maker are known
- replacement readiness is verified
- advisory or compulsory status is documented
- migration guide and support path exist
- consumers are migrated incrementally where needed
- removal happens only after zero active usage is verified
- old code, tests, docs, configuration, and notices are cleaned up
