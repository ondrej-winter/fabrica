---
name: interview-me
description: Reduce uncertainty about a user's underlying intent through a formal XY-problem gate plus a hypothesis, confidence, evidence, and information-gain interview loop. Use when an ask is underspecified, solution-led, or has material unresolved trade-offs before idea refinement, specification, planning, or implementation.
metadata:
  version: "1.2.0"
  dependencies:
    tools: []
    skills:
      - name: idea-refine
        purpose: Refine confirmed intent when the outcome is known but concept, options, or MVP boundary remain uncertain.
        required: false
      - name: spec-driven-development
        purpose: Convert confirmed intent into concrete requirements, scope, and acceptance criteria.
        required: false
      - name: planning-and-task-breakdown
        purpose: Break accepted requirements into ordered implementation tasks after specification.
        required: false
      - name: doubt-driven-development
        purpose: Adversarially review a decision or downstream artifact after intent has been established.
        required: false
      - name: source-driven-development
        purpose: Verify external, framework, or version-specific facts that affect a clarified decision.
        required: false
---

# Interview Me

Use this skill before planning, specification, or implementation when a stated
request may be a proxy for a different desired outcome. Treat intent discovery as
iterative uncertainty reduction: maintain an explicit model, ask the question
with the highest expected decision value, update the model from evidence, and do
not proceed on unrecorded assumptions.

## When to use this skill

Use this skill when:

- the ask lacks a material fact about the user, problem, outcome, success measure,
  scope boundary, constraint, decision owner, or deadline
- the request names a conventional solution, such as a dashboard, rewrite, AI
  feature, or scalable architecture, but not the outcome it must produce
- plausible interpretations lead to materially different requirements or paths
- the user asks to be interviewed, grilled, challenged, or stress-tested
- you would otherwise fill a material requirement gap with an unstated assumption

Do not use this skill when the outcome and boundaries already suffice for the
next decision, or for a mechanical edit, direct information request, typo, rename,
formatting operation, or similarly precise task. Use `idea-refine` when intent is
known but the option space needs exploration. Use `spec-driven-development` when
intent is known and requirements need definition.

## XY gate

Before treating a requested mechanism as a requirement, distinguish the stated
solution (Y) from the underlying outcome or problem it is meant to address (X).
The gate prevents optimizing a proposed answer before establishing the question.

1. State Y: the named artifact, technology, workflow, or implementation approach.
2. State X: the user outcome, decision, or problem; mark it as confirmed or
   hypothesized.
3. Set `XY-RISK` to `high` when X is missing or inferred, multiple plausible X
   values could justify Y, another solution could satisfy X with materially
   different cost, scope, risk, or architecture, or the user cannot name the
   decision or success signal Y enables.
4. Set `XY-RISK` to `medium` when X is plausible but material outcome, success,
   or constraint details remain unconfirmed.
5. Set `XY-RISK` to `low` only when the user has confirmed X and explained why Y
   is a required mechanism or constraint rather than a preferred option.

For high or medium risk, write the hypothesis in terms of X, retain Y as a
candidate option or constraint, and ask the highest-information-gain question
about X. Do not investigate, design, or commit to Y as though it were confirmed.
For low risk, record why Y is required and continue with the normal interview.

## Operating model

Maintain this state throughout the interview. Show it in the first turn and after
each answer that materially changes the model. Keep it concise, but do not hide
uncertainty.

```text
STATED SOLUTION (Y): <requested mechanism, artifact, or approach>
UNDERLYING OUTCOME (X): <confirmed or hypothesized problem, decision, or result>
XY-RISK: <low | medium | high> — <reason>
HYPOTHESIS: <current best statement of the intended outcome>
CONFIDENCE: <0-100%> — <why this level is justified>
EVIDENCE: <facts stated or confirmed by the user>
HIGH-IMPACT UNKNOWNS: <variables that could change the next decision>
NEXT QUESTION: <one question chosen to reduce the highest-impact uncertainty>
GUESS: <falsifiable predicted answer and its supporting evidence>
```

`I don't know` is a valid observation, not a sufficient state. Translate it into
named unknowns, their decision impact, and the next question most likely to
reduce that uncertainty. Clearly distinguish user evidence from agent inference.

Confidence means confidence that the intent statement is sufficient for the next
downstream decision. It is not a claim of psychological certainty or a substitute
for user confirmation.

| Confidence | Meaning | Required action |
| --- | --- | --- |
| 0-39% | Primary user, problem, or outcome is unclear. | Test the core interpretation before discussing solutions. |
| 40-69% | A direction is plausible, but material success, scope, or constraints are unresolved. | Ask the highest-information-gain question. |
| 70-89% | Intent is mostly clear; boundaries, success, or ownership still need confirmation. | Resolve or explicitly record remaining material unknowns. |
| 90-100% | The intent model is sufficient to restate for confirmation. | Present the intent artifact and request confirmation. |

Do not increase confidence merely because more words were exchanged. Increase it
only when evidence resolves, bounds, or explicitly accepts a high-impact unknown.
Decrease it when the user contradicts the model or reveals a competing objective.

## Steps

### 1. Apply the XY gate and form the initial model

State the best current hypothesis, confidence, and missing variables before asking
for implementation details. A hypothesis must be specific enough to be wrong.

```text
STATED SOLUTION (Y): Build a dashboard for metrics.
UNDERLYING OUTCOME (X): Track active experiments and decide which need attention; hypothesized.
XY-RISK: High — the user, decision, and success signal for the dashboard are unconfirmed.
HYPOTHESIS: You need a personal view of active experiments and their early results; a dashboard is a candidate interface, not a confirmed requirement.
CONFIDENCE: 30% — the user, desired decision, success signal, and data boundary are unknown.
EVIDENCE: The request asks for a dashboard for metrics.
HIGH-IMPACT UNKNOWNS: Who uses it; which decision it supports; what metrics matter; what is out of scope.
NEXT QUESTION: Who needs to make which recurring decision with this information?
GUESS: You are the primary user, because the request names neither a shared audience nor a reporting obligation.
```

Do not invent evidence. Label inferences as guesses and user statements as
evidence.

### 2. Choose the next question by information gain

Ask exactly one question, followed by one falsifiable guess. Prefer the question
whose possible answers would most change the next decision: route, scope,
requirements, success criteria, constraint, or implementation approach.

Prioritize unknowns in this order unless context shows another unknown has more
decision value:

1. primary user and problem or job to be done
2. intended outcome and measurable success signal
3. binding scope boundary, constraint, risk, deadline, or decision owner
4. trade-off between plausible directions
5. implementation detail that remains material after the preceding items

```text
Q: <one focused question>
GUESS: <one predicted answer, why it is plausible, and permission to reject it>
```

The guess must be falsifiable, evidence-based where possible, and non-manipulative.
It is a test of the model, not an attempt to steer the user toward a preferred
answer. Do not batch questions. Wait for the answer before selecting the next
highest-value unknown.

### 3. Update from evidence

After each answer:

1. distinguish confirmed evidence from inference
2. revise the hypothesis when evidence changes it
3. add, remove, or re-rank high-impact unknowns
4. update confidence only to the degree the evidence warrants
5. ask the next question only if a material unknown remains

Challenge ambiguous labels such as "scalable", "clean", "modern", or "best
practice" by asking for the decision, threshold, failure mode, or trade-off they
represent. When convention may be masking preference, ask:

```text
Q: If you did not need to justify the conventional solution, what result would you actually choose?
GUESS: The outcome matters more than preserving the named solution, because the request describes an artifact rather than a decision it enables.
```

When a user delegates a material choice with "whatever you think is best," record
the delegation as evidence, present the relevant options and consequences, then ask
them to choose or explicitly authorize an assumption. Delegation alone does not
resolve the trade-off.

### 4. Separate intent questions from factual questions

Clarify what the user wants before researching whether a technology, framework, or
external system can provide it. If a fact determines whether an otherwise clear
option is viable, record it as a dependency and use `source-driven-development` or
repository evidence to verify it.

```text
INTENT DECISION: The workflow must support offline use.
FACT TO VERIFY: Whether <platform_or_version> supports the required local storage and synchronization behavior.
```

Do not use a guessed technical fact to manufacture user intent, and do not turn a
user preference into a fact-finding exercise.

### 5. Restate and confirm intent

When confidence is at least 90%, every remaining high-impact unknown is resolved,
accepted as an explicit assumption, or recorded as a blocker, provide this artifact:

```text
STATUS: Confirmed intent | Intent draft — confirmation required

STATED SOLUTION (Y): <requested mechanism; required, candidate, or rejected>
UNDERLYING OUTCOME (X): <confirmed problem, decision, or result>
XY-RISK: <low | medium | high> — <resolution or remaining reason>
OUTCOME: <what must change or become possible>
PRIMARY USER: <who benefits or decides>
TRIGGER / WHY NOW: <event, pain, or opportunity>
SUCCESS SIGNALS: <observable, testable indicators>
CONSTRAINTS: <binding limits, risks, compatibility, deadline, or owner>
IN SCOPE: <required capabilities or decisions>
OUT OF SCOPE: <explicit exclusions>
ACCEPTED ASSUMPTIONS: <user-authorized assumptions, or none>
OPEN QUESTIONS / BLOCKERS: <unresolved items and impact, or none>
NEXT STEP: <idea-refine | spec-driven-development | source-driven-development | other>
```

Ask for direct confirmation. A clear approval of a concrete restate, including
"yes," "approved," or "sounds good; proceed," is confirmation. If the response
adds a material refinement, update and re-confirm. If the user is rushed, label
unresolved items rather than treating silence as acceptance.

## Stop condition

Stop interviewing when all of the following are true:

- the hypothesis identifies a user, outcome, success signals, constraints, and
  scope boundaries sufficient for the next decision
- no unresolved unknown would materially change the downstream route or artifact,
  unless explicitly recorded as an accepted assumption or blocker
- confidence is at least 90% and justified by user-provided evidence
- the user confirmed the concrete intent artifact, or it is clearly labeled an
  unconfirmed draft

As a secondary calibration check, ask whether you can predict the broad shape of
the user's reaction to the next three plausible questions. If not, locate the
missing variable and lower confidence. This heuristic must not override the
explicit readiness criteria.

If several rounds fail to reduce uncertainty, report the model state, identify the
foundational unknown blocking progress, and ask whether to change the decision,
provide more context, or proceed with an explicitly bounded assumption.

## Non-interactive contexts

This skill requires a live, responsive user for confirmation. Do not simulate an
interview in CI, scheduled jobs, autonomous runs, or other non-interactive
contexts. Instead, produce an `Intent draft — confirmation required` artifact
listing evidence, assumptions, high-impact open questions, and the fact that
implementation or accepted specification work is blocked pending confirmation.

## Verification and handoff

Before handing off, verify that:

- the first turn contained a falsifiable hypothesis, numeric confidence, evidence,
  high-impact unknowns, stated solution, underlying outcome, and XY-risk level
- a high- or medium-risk stated solution was treated as a candidate until the
  underlying outcome and its relationship to that solution were confirmed
- every question was singular and selected for expected decision value
- every guess was falsifiable and did not present an inference as user evidence
- confidence changed only in response to relevant evidence or contradiction
- the final artifact includes outcome, user, success signals, constraints, in
  scope, out of scope, assumptions, open questions, XY-gate result, status, and
  next step
- confirmation is explicit, or the artifact is labeled unconfirmed with its blocker
- the downstream skill follows the confirmed intent, not the original
  solution-shaped request

Use `idea-refine` when the outcome is confirmed but competing concepts or MVP
boundaries need exploration. Use `spec-driven-development` when the outcome is
confirmed and concrete requirements need definition. Use
`source-driven-development` when a verified external or version-specific fact is
needed to evaluate an identified option. Use `doubt-driven-development` after a
decision or downstream artifact exists and needs adversarial review.
