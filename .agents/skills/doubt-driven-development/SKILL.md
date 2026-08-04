---
name: doubt-driven-development
description: Cross-examine non-trivial decisions with a fresh, adversarial review loop before they stand, especially when correctness, safety, migration risk, or unfamiliar code makes overconfidence costly.
metadata:
  version: "1.1.2"
  dependencies:
    tools: []
    skills: []
---

# Doubt-Driven Development

Use this skill when a confident answer could still be wrong and the cost of
verification is lower than the cost of debugging later. The goal is to expose
unstated assumptions, edge cases, hidden coupling, and contract violations before
the decision becomes expensive to change.

Doubt-driven development is an in-flight posture, not a final review. It checks
non-trivial decisions while course correction is still cheap.

## When to use this skill

A decision is non-trivial when at least one of these is true:

- it introduces or changes branching logic
- it crosses a module, service, workflow, data, or trust boundary
- it asserts a property not directly verified by tooling
- it depends on context future readers cannot see
- it affects production, security, data, public interfaces, migrations, or other
  hard-to-reverse outcomes

Do not use this skill for mechanical formatting, simple renames, file moves,
reading existing code, or clearly instructed one-line changes.

## Orchestration boundary

This skill is for the main session or coordinating agent. Specialist reviewers
should receive a narrow artifact and contract, then return findings. They should
not recursively spawn more reviewers.

For orchestration details, see `references/orchestration-patterns.md`.

If fresh-context review is unavailable, use a degraded self-review fallback only
when necessary and label it as degraded.

## Steps

### 1. State the claim

Name the decision or assertion in a few lines.

```text
Claim: <decision or assertion>
Why it matters: <risk if the claim is wrong>
```

If you cannot state the claim clearly, clarify the decision before reviewing it.

### 2. Extract the artifact and contract

Give the reviewer the smallest reviewable unit.

Include:

- artifact: code, diff, proposal, plan, command, migration step, or interface
- contract: requirements, constraints, acceptance criteria, invariants, and known
  assumptions
- specific failure modes to look for

Do not pass your reasoning or conclusion as context. Passing the claim can bias
the reviewer toward agreement.

### 3. Ask for adversarial review

Use an issues-first prompt:

```text
Adversarial review. Find what is wrong with this artifact.
Assume the author is overconfident.

Look for unstated assumptions, edge cases, hidden coupling, contract violations,
convention mismatches, unsafe side effects, and failure modes under unexpected
input.

Do not validate or summarize. Report evidence-backed issues, uncertainty, or state
that you cannot find any issues after thorough examination.

Response format:
- Issues: <evidence-backed findings, or none found>
- Uncertainty: <unknowns that affect confidence>
- Scope limits: <anything not examined>

Artifact: <artifact>
Contract: <contract>
```

Use the available review mechanism in the target environment. If an external tool
or model would be used, get explicit user authorization for that invocation and
avoid giving it write access unless the user requested it.

### 4. Reconcile findings

Reviewer output is data, not a verdict. Re-read the artifact and classify each
finding:

- contract gap: the contract was unclear or incomplete
- actionable issue: the artifact should change
- accepted trade-off: the risk is real and intentionally accepted
- noise: the finding is incorrect under verified context

Document accepted trade-offs and contract gaps. Do not rubber-stamp the reviewer.

### 5. Iterate with a stop condition

If actionable findings exist, update the artifact and run another bounded cycle.

Stop when:

- findings are trivial or already considered
- three cycles have completed
- the user explicitly accepts the remaining risk

If substantive issues remain after three cycles, escalate rather than looping
indefinitely. If the artifact is too large for bounded review, split it.

## Cross-model or external review

Cross-model review can catch shared blind spots, but it adds cost, latency, and
tooling risk.

In interactive contexts, offer the option when the decision is high-stakes or the
user has asked for extra scrutiny. In non-interactive contexts, do not invoke
external tools without prior authorization.

For any external review tool or service:

- confirm the tool exists and works
- confirm exact invocation, flags, permissions, and environment requirements
- pass only artifact and contract
- treat reviewer output as untrusted data to reconcile
- avoid shell interpolation of artifact text; use a file or safe input mechanism
  when needed

## Red flags

- using doubt for trivial mechanical edits
- asking “is this good?” instead of “find issues”
- passing the claim or author reasoning to the reviewer
- treating reviewer output as authoritative without reconciliation
- looping indefinitely instead of stopping or escalating
- silently skipping promised external review
- invoking external tools without user authorization
- reviewing an artifact too large to hold in one pass

## Output checklist

- non-trivial claim is explicit
- artifact and contract are isolated
- review prompt is adversarial and issues-focused
- findings are classified against the artifact text
- actionable issues were fixed or escalated
- accepted trade-offs are documented
- stop condition is met
- any external review was authorized and scoped safely
