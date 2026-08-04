---
name: idea-refine
description: Refine raw ideas into actionable concepts through divergent exploration, convergent evaluation, assumption testing, and a final one-page brief. Use when an idea is vague, over-scoped, solution-led, or needs pressure-testing before planning or implementation.
metadata:
  version: "1.0.5"
  dependencies:
    tools:
      - name: sh
        purpose: Run the optional local idea refinement helper script when available.
        required: false
    skills:
      - name: interview-me
        purpose: Clarify unclear user intent before refining rough concepts into options.
        required: false
      - name: spec-driven-development
        purpose: Convert a refined direction into concrete requirements and acceptance criteria.
        required: false
---

# Idea Refine

Use this skill when the user has an idea but not yet a sharp concept worth
planning or building. The goal is to help the user widen the option space, choose
a promising direction, surface the assumptions that could kill it, and leave with
a concise artifact that supports the next decision.

## When to use this skill

Use this skill when:

- the idea is promising but vague
- the user is anchored on a solution before the problem is clear
- several possible directions exist and the user needs help choosing
- a plan needs stress-testing before implementation
- the user asks to ideate, refine an idea, sharpen a concept, or stress-test a
  plan

Do not use this skill when:

- the user needs a direct implementation of a clear request
- the task is a mechanical edit, bug fix, rename, or formatting pass
- the user has already provided a validated concept and wants execution planning
- there is no live user available to answer clarifying questions

Use `interview-me` first when the underlying intent is still uncertain or the
request may be a conventional proxy for a different outcome. Use this skill when
the intent is understood but the concept, options, assumptions, or MVP boundary
need refinement. Use `spec-driven-development` after the user confirms the chosen
direction and the work needs concrete requirements, success criteria, and an
implementation plan.

## Steps

### 1. Frame the idea

Restate the idea as a clear problem opportunity, preferably in this form:

```text
How might we <create outcome> for <specific user> without <key constraint or trade-off>?
```

Then ask three to five sharpening questions. Ask only what is needed to continue.
Do not proceed until you understand at least:

- who the idea is for
- what success would look like
- which constraint matters most

Useful questions include:

- Who has this problem right now?
- What are they doing today instead?
- What would make this meaningfully better than the current workaround?
- Why now?
- What must stay small, cheap, fast, private, compatible, or simple?

If you are working inside an existing project, inspect relevant files and patterns
before generating directions. Treat the current architecture, data model,
interfaces, and team conventions as both constraints and sources of leverage.

### 2. Expand the option space

Generate five to eight distinct idea variations. Each variation should explain why
it exists, not just what it is.

Use lenses such as:

- inversion: what if the opposite approach worked better?
- simplification: what is the version that is ten times smaller?
- constraint removal: what would change if budget, time, or technology were not
  limiting?
- constraint addition: what if it had to work in one day, with one feature, or
  without the obvious tool?
- audience shift: what changes for a different or narrower user?
- combination: what adjacent idea makes this stronger?
- expert lens: what would a domain expert find obvious that outsiders miss?

Use `references/frameworks.md` for additional ideation lenses. Select the few that
fit the idea; do not run every framework mechanically.

### 3. Converge on directions

After the user reacts to the variations, group the strongest options into two or
three distinct directions. Each direction should represent a real strategic
choice, not a minor feature variation.

Evaluate each direction against:

- user value: who benefits, how much, and how often?
- feasibility: what is hard technically, operationally, legally, or socially?
- differentiation: why would someone choose this over the current workaround?

Use `references/refinement-criteria.md` for the fuller rubric when the trade-off is
not obvious.

Be honest rather than merely supportive. If a direction is weak, say why with
specificity and offer a sharper alternative.

### 4. Audit assumptions

Before recommending a direction, name the assumptions behind it.

For each serious direction, identify:

- what must be true for it to work
- what could kill it
- what can be ignored for now
- the smallest practical test for the riskiest assumption

Prefer assumptions that can be validated through direct user behavior, interviews,
manual prototypes, concierge tests, or small code spikes. Avoid treating internal
confidence as validation.

### 5. Produce the one-page brief

Once the user confirms the recommended direction, produce a concise markdown brief:

```md
# <Idea Name>

## Problem Statement

<One-sentence How Might We framing.>

## Recommended Direction

<Chosen direction and why. Keep this to two or three short paragraphs.>

## Key Assumptions to Validate

- [ ] <Assumption and proposed test>
- [ ] <Assumption and proposed test>
- [ ] <Assumption and proposed test>

## MVP Scope

<Minimum version that tests the core assumption. Include what is in and out.>

## Not Doing and Why

- <Cut scope> — <reason>
- <Cut scope> — <reason>
- <Cut scope> — <reason>

## Open Questions

- <Question that must be answered before building>
```

The `Not Doing and Why` section is mandatory. It turns focus into explicit
trade-offs and prevents a good idea from becoming a bloated plan.

Offer to save the brief to `docs/ideas/<idea-name>.md` or another user-chosen
location. Save only after the user confirms.

## Optional helper

The script at `scripts/idea-refine.sh` creates an idea brief directory and prints
a JSON status line. It defaults to `docs/ideas/` and accepts an optional directory
argument. Use it only when the user wants to persist idea briefs in the current
workspace.

## References

- `references/frameworks.md` lists optional ideation frameworks.
- `references/refinement-criteria.md` provides a convergence evaluation rubric.
- `references/examples.md` shows example sessions and one-page briefs.

## Red flags

- generating many shallow ideas instead of five to eight considered variations
- skipping the target user or success criteria
- treating the first plausible solution as the recommendation
- avoiding hard feedback because the user seems excited
- producing a build plan before assumptions are surfaced
- omitting the `Not Doing and Why` section
- ignoring existing codebase constraints when refining a project-specific idea
- saving a brief before the user confirms the final direction and location

## Verification

- the idea was reframed as a clear problem opportunity
- the target user, success criteria, and binding constraint are known
- multiple directions were explored before converging
- weak directions were challenged with specific reasons
- hidden assumptions and validation tests were listed
- the recommended MVP tests the riskiest assumption first
- the final brief includes a concrete `Not Doing and Why` section
- the user confirmed the direction before any implementation planning began
