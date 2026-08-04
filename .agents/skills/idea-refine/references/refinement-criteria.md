# Refinement and Evaluation Criteria

Use this rubric during convergence. Not every dimension matters equally for every
idea; choose the criteria that expose the most important trade-offs.

## User value

If value is unclear, nothing else matters.

Distinguish painkillers from vitamins:

- Painkiller: solves an acute or frequent problem, replaces a painful workaround,
  and creates urgency.
- Vitamin: sounds useful but does not change behavior.

Ask:

- Can the user name specific people who have this problem now?
- What are those people doing today instead?
- How often does the problem occur?
- What would make them switch?
- Is demand being pulled by users or pushed by the builder?

Red flags:

- the target user is described as everyone
- the idea is only a marginal improvement over a tolerated workaround
- the problem is intense but too rare to support the proposed effort

## Feasibility

Feasibility includes technology, resources, time, trust, regulation, operations,
and adoption.

Ask:

- Does the core technology already work reliably enough?
- What is the hardest part, and is it known-hard or merely unfamiliar?
- Which third parties, APIs, data sources, or permissions must cooperate?
- What is the smallest team and timeframe that could test the concept?
- Can value reach users in days or weeks rather than months?

Red flags:

- the MVP requires solving a research problem first
- several dependencies all need to work at the same time
- the minimum useful version is still large

## Differentiation

Differentiation means different in a way users care about, not merely better in a
way builders admire.

Ask:

- What would a user tell a friend this does?
- What can this do that current workarounds cannot?
- Is the difference durable enough to matter?
- Is the difference visible in the user experience?

Common differentiation types, from stronger to weaker:

1. new capability
2. ten-times improvement on a key dimension
3. new audience
4. new context where existing solutions fail
5. dramatically simpler experience
6. lower cost

Red flags:

- differentiation is mostly technical rather than experiential
- the claim is faster, cheaper, or prettier without a structural reason
- the unique feature is not the feature users value most

## Assumption audit

Classify assumptions by severity.

### Must be true

If these assumptions are wrong, the idea fails. Validate them before building.

Example: users will share the data the product requires.

### Should be true

If these assumptions are wrong, the strategy changes but the core idea may survive.

Example: users prefer self-serve onboarding over guided setup.

### Might be true

These assumptions affect secondary features or optimizations. Do not validate them
before the core value is proven.

Example: users will want to share results with teammates.

## Decision matrix

Use this simple matrix when choosing between directions:

|            | High feasibility | Low feasibility |
| ---------- | ---------------- | --------------- |
| High value | Do this first    | Worth the risk  |
| Low value  | Only if trivial  | Do not do this  |

Use differentiation as the tiebreaker between options in the same quadrant.

## MVP scoping principles

- Do one job well.
- Test the riskiest assumption first.
- Prefer a time box over a feature wish list.
- Make the `Not Doing and Why` section explicit.
- If the first version feels complete to the builder, it is probably too large.
