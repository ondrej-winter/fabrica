# Ideation Session Examples

These examples show the rhythm of a good idea-refinement session. Study the
framing, trade-offs, and pushback more than the specific ideas.

## Example 1: Vague early-stage concept

User idea:

```text
I want to help small local restaurants compete with the big delivery platforms.
```

Strong first response:

```text
How might we help independent restaurants keep profitable customer relationships
without forcing them into a delivery-platform model that erodes their margins and
brand?

Before expanding, I need to know three things:

1. Which part of competing matters most: customer acquisition, ordering,
   delivery, retention, or platform fees?
2. Who is the primary user: the owner, staff, diner, or neighborhood community?
3. What must stay true for this to be realistic: software-only, low setup, no new
   delivery operations, or something else?
```

After the user says restaurant owners are paying high commissions but cannot leave
because platforms own customer demand, a good expansion might include:

- Direct ordering for existing customers, because competing for repeat orders is
  easier than competing for discovery.
- A regulars-only reorder flow, because a restaurant's best customers may be the
  highest-leverage audience.
- Pickup-first ordering, because delivery is the expensive operational burden.
- A neighborhood restaurant collective, because local restaurants have weak
  individual marketing power but stronger combined demand.
- SMS-first reordering, because a busy owner should not have to manage another
  dashboard.

Good convergence:

```text
The sharper bet is not "build another ordering platform." It is "help restaurants
move their best repeat customers to direct reorder behavior." That is narrower,
more differentiated, and tests the real business value faster.
```

Example one-page brief excerpt:

```md
# Regulars Reorder Engine

## Problem Statement

How might we help independent restaurants retain their best repeat customers
through direct ordering without adding operational burden?

## Recommended Direction

Build an SMS-first reorder tool for a restaurant's known regulars. Do not start as
a marketplace, full ordering platform, or delivery operation.

The wedge is commission avoidance on customers the restaurant already earned. The
tool should require minimal owner effort and make the customer's next reorder feel
easier than opening a delivery app.

## Key Assumptions to Validate

- [ ] Repeat customers will reorder through SMS or a direct link instead of their
      usual delivery app. Test with five restaurants and twenty regulars each.
- [ ] Owners can identify enough regulars and are willing to invite them. Test in
      ten owner interviews.
- [ ] Commission savings justify setup effort. Test willingness to pay or run a
      concierge pilot.

## MVP Scope

SMS reorder prompts, manual owner setup for regulars, pickup-only orders, payment
link, and simple order notification.

## Not Doing and Why

- Delivery logistics — too operationally heavy for the core assumption.
- Marketplace discovery — competing with platform demand is not the wedge.
- POS integration — useful later, but manual setup is enough to test demand.
```

## Example 2: Feature idea in an existing product

User idea:

```text
Add real-time collaboration to our document editor.
```

Codebase-aware refinement should inspect the relevant editor, persistence, and
transport patterns before proposing directions. If the codebase uses block-based
documents and has no real-time infrastructure, say so and let that shape the
options.

Useful variations:

- Presence only: show who is viewing or editing sections without enabling
  simultaneous editing.
- Block-level locking: allow real-time work in different blocks without complex
  conflict resolution.
- Async suggestions: make collaboration review-based instead of live-editing.
- Version branches: let collaborators propose separate changes and merge later.

Good pushback:

```text
This may be a competitive checkbox rather than a differentiator. If the goal is to
stop losing deals, the best MVP may be the simplest collaboration behavior that
customers recognize as real-time, not a full character-level conflict system.
```

Strong `Not Doing and Why` entries might include:

- character-level CRDTs, because block-level collaboration may satisfy the user
  need at much lower complexity
- offline sync, because it does not test whether users value live collaboration
- AI collaboration, because it changes the problem rather than validating the
  requested capability

## Example 3: Process or workflow idea

User idea:

```text
Find a better way to run weekly team retrospectives. They have gotten stale and
people dread them.
```

Good reframing:

```text
How might we make retrospectives produce visible improvement for the team instead
of becoming a recurring meeting people endure?
```

If the user says action items pile up and nothing changes, the strongest insight is
that the meeting may not be stale; the output loop is broken.

Useful variations:

- one action item maximum, with an owner and deadline
- next retro starts with a five-minute demo of the previous action
- async written input, then a short decision meeting
- anonymous topic collection to include quieter participants
- each retro output becomes a two-week experiment with a success measure

Good convergence:

```text
Start by fixing follow-through, not by buying a new tool or inventing a complex
facilitation format. The first experiment should cost nothing and change one
behavior: every retro produces at most one visible improvement.
```

Strong `Not Doing and Why` entries might include:

- new retro software, because tooling is not the bottleneck
- elaborate facilitation formats, because process novelty may hide the output
  problem
- multiple action items, because a pile of good intentions is exactly what is
  failing now

## What strong sessions have in common

- The restatement changes the frame from a solution to a problem.
- Questions diagnose before prescribing.
- Variations explain why they exist.
- The agent has opinions and states trade-offs clearly.
- Weak ideas are challenged with specific reasons.
- The output names actions, assumptions, and excluded scope.
- The final brief fits the domain, whether the idea is a product, feature,
  process, policy, or technical direction.
