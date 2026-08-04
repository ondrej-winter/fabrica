---
name: ci-cd-and-automation
description: Design, review, or improve CI/CD and automation workflows for quality gates, deployment safety, rollback readiness, secrets handling, and feedback loops across any technology stack.
metadata:
  version: "1.5.0"
  dependencies:
    tools: []
    skills: []
---

# CI/CD and Automation

Use this skill when setting up, reviewing, or changing automated workflows that
build, test, verify, release, deploy, or maintain a project. The goal is to make
verification repeatable, failures actionable, and releases reversible.

CI/CD should enforce the project’s quality expectations without assuming a
specific language, package manager, repository host, CI provider, deployment
platform, or test framework.

## When to use this skill

Use this skill when you need to:

- create or modify a CI pipeline
- add automated quality gates
- configure deployment, preview, staging, or release workflows
- debug failed automated checks
- improve feedback loops between CI failures and development work
- add rollback, feature flag, dependency update, or scheduled maintenance
  automation

Do not use this skill to bypass project quality gates. If a gate is too noisy or
too slow, fix the gate or document a temporary exception with ownership and an
expiry condition.

## Principles

- Catch problems as early as practical. Prefer static checks before slower tests,
  tests before staging, and staging before production.
- Keep batches small. Smaller changes and frequent releases are easier to debug
  and safer to roll back.
- Make automation reproducible locally where practical. A failing CI step should
  point to a command or procedure a maintainer can run before pushing again.
- Treat secrets and deployment permissions as production-sensitive, even in test
  pipelines.
- Optimize slow pipelines by improving structure, caching, or test selection, not
  by silently skipping important checks.

## Steps

### 1. Identify the workflow and trigger

Define what automation is needed and when it runs.

Capture:

- trigger, such as proposed change, merge, tag, scheduled run, manual dispatch,
  or deployment event
- target environment, such as local verification, CI, staging, preview, or
  production
- required inputs, secrets, permissions, and artifacts
- expected pass/fail signal
- who owns failures and how they are handled

### 2. Define quality gates

Use the project’s existing commands when available. If commands are missing,
document placeholders in the design and call out that concrete tooling must be
chosen before the gate can run.

Common gates include:

- formatting or style check: `<format_check_command>`
- lint or static analysis: `<lint_command>`
- type, schema, or contract validation: `<contract_check_command>`
- unit tests: `<unit_test_command>`
- integration tests: `<integration_test_command>`
- end-to-end or smoke tests: `<e2e_or_smoke_test_command>`
- build or package verification: `<build_command>`
- security, dependency, or image scan: `<security_scan_command>`
- documentation, migration, or generated-file drift check:
  `<repository_validation_command>`

Order fast deterministic checks before slower or environment-heavy checks.

For Python type-checking gates, use the project's configured `ty` command when
present. If the target project has not selected a type checker and the workflow
must introduce one, prefer `ty` rather than `mypy`. Run it through the project's
declared dependency and command mechanism so local and CI execution use the same
version; do not assume a globally installed executable. Treat replacement of an
established checker as an explicit migration rather than incidental CI cleanup.

### 3. Keep provider configuration portable

Use the project’s CI provider conventions, but keep the design independent of a
single provider whenever possible.

For each job, define:

- checkout or source acquisition step
- runtime, toolchain, or container setup
- dependency installation or cache restoration
- command to run
- artifacts to collect on success or failure
- secrets and permissions required
- timeout and retry policy
- concurrency and cancellation behavior for duplicate or superseded runs
- trust, pinning, and update policy for third-party actions, images, or plugins

Provider-specific YAML, hosted runner names, and marketplace actions are examples,
not portable requirements. Scope them as examples when documenting reusable skill
guidance.

### 4. Make failures actionable

When CI fails, preserve enough information for a maintainer or agent to reproduce
and fix the issue.

For each failure path, include:

- the exact failing command or check name
- relevant logs or artifacts
- environment details that affect reproduction
- whether the failure is deterministic or flaky
- the local command or next diagnostic step

Useful failure prompts include:

```text
The automated check `<check_name>` failed with this output:
<error_output>

Reproduce locally with `<local_command>`, fix the issue, and rerun the relevant
quality gate before pushing again.
```

Do not normalize flaky failures by rerunning indefinitely. Track and fix the
source of flakiness.

### 5. Protect secrets and environments

Keep secrets out of committed files, logs, artifacts, and client-visible output.

Check that:

- secrets come from the CI provider, vault, or deployment platform secret store
- CI and production use separate credentials
- least-privilege permissions are used for jobs and tokens
- forks or untrusted changes cannot access sensitive secrets unexpectedly
- test credentials are clearly scoped and cannot affect production resources
- logs and artifacts do not expose credentials, tokens, or sensitive data

Configuration templates may be committed, but real secrets must not be.

### 6. Design deployment and release safety

For deployment workflows, define:

- artifact or version being deployed
- how the same immutable artifact is promoted between environments
- target environment and approval requirements
- migration steps and ordering
- smoke checks or health checks after deployment
- monitoring window and success criteria
- rollback or roll-forward procedure
- concurrency rules that prevent overlapping deployments from corrupting state
- ownership when deployment fails

For risky or incomplete functionality, consider feature flags, staged rollout,
canary deployment, or preview environments. Document the lifecycle and cleanup
date for temporary flags or release switches.

### 7. Automate maintenance carefully

Automation beyond CI can reduce operational toil when it has clear ownership.

Examples include:

- dependency update proposals
- vulnerability scans
- scheduled test suites
- generated documentation or schema drift checks
- repository health reports
- stale preview cleanup

For each automation, define what it changes, who reviews the result, and how to
recover if the automation behaves incorrectly. Test mutating automation with a
dry-run mode, disposable environment, or tightly bounded scope when practical.

### 8. Optimize without weakening the gate

When automation becomes too slow, improve the pipeline before removing checks.

Prefer:

- caching dependencies or build outputs with safe cache keys
- splitting independent jobs to run in parallel
- running only relevant checks for clearly scoped changes
- sharding large test suites
- moving slow non-critical checks to scheduled runs while keeping a representative
  smoke check on each proposed change
- using faster runners or build infrastructure when justified

Document any skipped or deferred gate with the risk, owner, and expiry condition.

### 9. Verify the automation itself

After changing automation, verify that it runs in the intended environment.

Confirm:

- the workflow triggers on the intended events
- workflow configuration syntax, schema, or provider linting passes when the
  provider offers a non-destructive validation command
- required gates run and block unsafe merges or deployments
- secrets are not exposed
- artifacts and logs are available when needed
- rollback or recovery path is documented and tested where practical
- mutating automation has been exercised safely before it can affect production
- local reproduction instructions exist for likely failures
- any gate that cannot be run before handoff is documented with the reason,
  risk, owner, and follow-up condition

## Red flags

- no automated verification for changes that affect shipped behavior
- quality gates disabled instead of fixed
- CI-only failures that cannot be reproduced or diagnosed
- secrets committed, logged, or exposed to untrusted jobs
- deployment without health checks, monitoring, or rollback plan
- production and test environments sharing credentials
- long-running pipelines with no optimization plan
- flaky tests treated as normal pipeline behavior

## Output checklist

- workflow trigger and owner are explicit
- quality gates use project commands or clear placeholders
- provider-specific configuration is scoped to the target project
- failures produce actionable logs and reproduction steps
- secrets and permissions follow least privilege
- deployment workflows include health checks and rollback guidance
- maintenance automation has review and recovery paths
- validation was run or skipped validation is documented
