# ADR 0001: Experimental Agent Skill Script Execution

## Status

Accepted

## Context

The subscription-backed Python agent runtime can already load selected Agent Skills context and evaluate policy for explicitly selected skill scripts. Actual script execution crosses a materially different safety boundary: local scripts can read files, start processes, consume resources, and expose secrets if execution is not tightly constrained.

This project needs a narrow implementation spike to validate application boundaries for script execution without implying production-grade sandboxing or full Agent Skills support.

## Decision

We will add experimental selected-script execution behind application-owned ports and outbound adapters.

Execution must be selected-only: callers provide an explicit `SelectedSkillScript`; the runtime must not automatically discover scripts or let models choose scripts to execute.

Execution must require `EvaluateSkillScriptPolicy` approval for the same metadata-bound `SkillScriptApprovalBinding` before an execution adapter is called. Approvals cannot be reused when script metadata changes.

The first execution scope is limited to `.py` and `.sh` scripts. Future local subprocess execution must use explicit interpreter argument lists with `shell=False`; shell scripts may be invoked through an explicit POSIX shell interpreter such as `/bin/sh <script>`, but must not use shell expansion.

The default execution policy intent is deny-by-default:

- no inherited user environment or secrets
- no network capability requested by the application policy
- no ambient caller working directory inheritance
- an execution-specific temporary working directory by default
- bounded timeout and bounded stdout/stderr capture
- safe, bounded observations only

## Non-goals

This decision does not provide production sandboxing. Process-level constraints such as timeouts, explicit interpreters, bounded output, and empty environments are not equivalent to OS/container isolation.

This decision does not add model-driven tool calls, tool-result loops, automatic skill discovery, live Codex/backend integration, or execution of real user skill directories in default tests.

## Consequences

Application code owns execution commands, results, statuses, and policy-gated orchestration. Subprocess, filesystem paths, interpreter discovery, environment handling, and temporary directory management remain adapter responsibilities.

Default tests must use synthetic scripts and fakes only. They must not read real user skill directories, run real user scripts, require subscription credentials, or call live backends.

Future production-ready execution requires a separate sandboxing decision and implementation, likely including OS/container isolation, network controls, filesystem controls, resource limits, and operational monitoring.
