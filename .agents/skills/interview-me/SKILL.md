---
name: interview-me
description: Uncover what the user actually wants instead of what they think they should want by interviewing them one question at a time until reaching about 95% confidence in the underlying intent. Use when an ask is underspecified ("build me X" without "for whom" or "why now"), when the user explicitly asks to be interviewed or have their thinking stress-tested, or when you catch yourself silently filling in ambiguous requirements before any plan, spec, or code exists.
metadata:
  version: "1.0.4"
  dependencies:
    tools: []
    skills:
      - name: idea-refine
        purpose: Refine the confirmed intent when the user knows the desired outcome but not the scope or concept boundary.
        required: false
      - name: spec-driven-development
        purpose: Convert confirmed concrete intent into requirements.
        required: false
      - name: planning-and-task-breakdown
        purpose: Break down work after confirmed intent has been written as a specification.
        required: false
      - name: doubt-driven-development
        purpose: Review downstream artifacts after a decision or draft exists.
        required: false
      - name: source-driven-development
        purpose: Verify framework or source facts after clarifying what the user wants.
        required: false
---

# Interview Me

Use this skill before planning, specification, or implementation when the user's
stated request may differ from the underlying outcome they actually want. The
goal is to interview one question at a time until there is a confirmed statement
of intent.

## Overview

What people ask for and what they actually want are different things. They ask
for "a dashboard" because that is what one asks for, not necessarily because a
dashboard solves their problem. They say "make it faster" without a number to
hit.

The cheapest moment to find this gap is before any plan, spec, or code exists.
Once building starts, switching costs are real, and the user may rationalize the
wrong thing into a "good enough" thing. The misfit gets locked in.

This skill closes the gap before it costs anything. Other define-phase skills
assume you already roughly know what you want. Use this skill before those, when
you need to ask one question at a time, with your best guess attached, until you
can predict what the user is going to say before they say it.

## When to use this skill

Use this skill when:

- the ask is missing at least one of: who the user is, why they want it, what
  success looks like, or what the binding constraint is
- the request is conventional rather than specific, such as "build me X" or
  "make it faster", and you cannot unpack the convention without guessing
- you are tempted to start with assumptions you have not surfaced
- the user has not said which value they are optimizing for when two reasonable
  ones are in tension, such as simplicity vs. flexibility or cost vs. speed
- the user explicitly invokes phrases like "interview me", "grill me", "before
  we start, are we sure?", or "stress-test my thinking"

Do not use this skill when:

- the ask is unambiguous and self-contained, such as "rename this variable" or
  "fix this typo"
- the user has explicitly asked for speed over verification
- the user is asking a pure information request, such as "how does X work?" or
  "what does this code do?"
- the task is a mechanical operation, such as a rename, format, or file move
- you already have at least 95% confidence about the underlying intent

## Loading constraints

This skill needs a live, responsive user. Do not invoke it in non-interactive
contexts like CI pipelines, scheduled runs, loops, or autonomous runs. If you are
in one of those contexts and the ask is underspecified, flag that as a blocker
for the user instead of guessing.

## Steps

### 1. Hypothesize with a confidence number

Before asking anything, write down your current best read of what the user wants
in one sentence, plus an honest confidence number from 0 to 100%.

```text
HYPOTHESIS: You want a way to answer "how are we doing?" in standup, and "dashboard" was the convention that came to mind.
CONFIDENCE: ~30% — missing: who it is for, what "metrics" means in context, and what success looks like
```

The number forces honesty. If you write down a high number but cannot actually
predict the user's reactions to the next three questions you would ask, the
number is wrong. Start at the confidence level you can defend.

When confidence is below about 70%, append a brief reason on the same line. State
what is still unresolved or missing so the user can help close the gap.

### 2. Ask one question at a time, each with a guess attached

Use this format:

```text
Q: <one focused question>
GUESS: <your hypothesis for the answer, with the reasoning that produced it>
```

Wait for the user to react before asking the next question.

Ask one question at a time because:

- the user cannot react to your hypotheses if you bury them in a list
- batches encourage skim-reading and surface answers
- later questions often depend on earlier answers
- the user's energy for thinking carefully is finite

Attach a guess because:

- the user reacts faster to a wrong guess than they generate an answer from
  scratch
- it commits you to a hypothesis you can be visibly wrong about
- it surfaces your assumptions, which is what the interview is meant to expose

The risk is that a polite user agrees with your guess to be agreeable. Mitigate
that by being visibly willing to be wrong, and occasionally guessing in a
direction you expect the user to push back on.

### 3. Listen for want vs. should want

The most dangerous answers are the ones where the user says what a thoughtful
answer sounds like rather than what they actually want. Watch for:

- answers that pattern-match best-practice talk, such as "scalable" or "clean
  architecture", without specifics
- answers that defer to convention, such as "the way most apps do it" or "the
  standard approach"
- phrases like "I should probably", "I think I am supposed to", or "good
  engineering practice says"
- buzzwords as goals, such as "modern", "scalable", or "robust", instead of a
  specific outcome

When you hear these, ask:

```text
If you did not have to justify this to anyone, what would you actually want?
```

That question often does more work than the previous five.

### 4. Restate intent in the user's own words

When your confidence is high, write back what you now think the user wants. Keep
it tight, use their language where possible, and structure it so the user can
confirm or correct line by line.

```text
Here is what I now think you want:

- Outcome:      <one line>
- User:         <one line — who benefits>
- Why now:      <one line — what changed>
- Success:      <one line — how we know it worked>
- Constraint:   <one line — the binding limit>
- Out of scope: <one line — what we are explicitly not doing>

Yes / no / refine?
```

Including "Out of scope" is required. Silent disagreement about what is not being
built is a common source of misalignment.

### 5. Confirm with an explicit yes

The gate is an explicit "yes." The following are not yes:

- "Whatever you think is best." The user is delegating, which means they do not
  have 95% confidence either. Re-ask with two concrete options framed as a
  choice.
- "Sounds good." Ask: "Anything you would refine?" Silence is not confirmation.
- "Sure, let's go." Treat this as a possible polite exit, not an endorsement.
- Silence followed by "okay let's start." The user may have given up on the
  interview, not converged.

If the user corrects you, fold the correction in and restate. Loop until you get
an explicit yes.

## Stop condition

You are done when you can answer yes to this question:

```text
Can I predict the user's reaction to the next three questions I would ask?
```

If yes, you have shared understanding. Stop interviewing and produce the restate.
If no, ask the next question.

If you have gone several rounds and still cannot predict the user's reactions,
stop and tell the user: "I have asked X questions and I still cannot predict your
reactions. Something foundational is missing. Want to step back?"

## Output

The output of this skill is a confirmed statement of intent: the restate from
Step 4, with an explicit yes from Step 5. Specs, plans, and task lists are
downstream; they consume the intent this skill produces.

If the user wants the intent to persist for a multi-session project or a handoff
to another collaborator, offer to save it to an appropriate project location,
such as an intent note, decision record, planning document, or issue. Only save
if they confirm.

## Example

Without this skill:

```text
User: build me a dashboard for our metrics
Agent: <starts proposing chart libraries and layouts>
```

The agent has assumed who it is for, what metrics are in scope, what "our team"
means, and what success looks like.

With this skill:

```text
User: build me a dashboard for our metrics

Agent:
HYPOTHESIS: You want a way to answer "how are we doing?" in standup, and "dashboard" came to mind because that is the conventional answer.
CONFIDENCE: ~30% — missing: who it is for, what "metrics" are, and what success looks like

Q: When you say "how are we doing?", who is asking: you alone, the engineering team in standup, or up the chain?
GUESS: Engineering team in standup, because "we" usually scopes that way and standups are where this question gets asked. If it is for executives, the metrics and framing change a lot.

User: It is actually for me. I keep losing track of which experiments are running and what their early signal looks like.

Agent:
Updated read: not a team dashboard at all. It is a personal experiment tracker.
Confidence: ~60% — still missing: what "early signal" means and what done looks like.

Q: Is the gap that you do not know which experiments exist, or that you cannot see their results in one place?
GUESS: The second one. You have a list of experiments somewhere, but their results live in five different tools, and reconciling them by hand is what you are tired of.

User: First one actually. I literally do not have a list. They are spread across different docs.
```

Two questions in, the agent has discovered the actual ask is not "a dashboard."
It is "a list." Different artifact, different scope, different work.

## Interaction with other skills

- `idea-refine`: downstream. If the confirmed intent is "I want X but I do not
  know how to scope it," hand off to idea refinement.
- `spec-driven-development`: downstream. If the confirmed intent is concrete,
  write it down as requirements.
- `planning-and-task-breakdown`: two hops downstream after the specification.
- `doubt-driven-development`: opposite end of the timeline. This skill is
  pre-decision intent extraction; doubt-driven review is post-decision artifact
  review.
- `source-driven-development`: orthogonal. This skill clarifies what the user
  wants; source-driven development verifies framework facts.

## Common rationalizations

- "The ask is clear enough": If you cannot write the user's desired outcome in
  one sentence right now, the ask is not clear. Run Step 1 before deciding.
- "Asking too many questions wastes their time": Time wasted by several targeted
  questions is small. Time wasted by building the wrong thing is enormous.
- "I will figure it out as I build": Switching costs after code exists are much
  higher than they are now. Discovery during implementation is rework.
- "They said whatever you think, so I should just decide": "Whatever you think"
  is delegation, not decision. Re-ask with two concrete options as a choice.
- "I should give them several options to pick from": Options work when the user
  knows what they want and is choosing between trade-offs. If they do not know
  what they want yet, listing options widens the search.
- "If I attach my guess, I am leading them": Leading is the point. Reacting is
  faster than generating from scratch. The risk is sycophancy, not leading.
- "We have talked enough, I get it": Test it: can you predict their reaction to
  the next three questions? If not, you do not get it yet.
- "The user said yes, we are done": If the yes followed a vague restate or an
  open-ended "sounds good," the yes is hollow. Restate concretely and re-confirm.

## Red flags

- three or more questions in a single message
- a question without your hypothesis attached
- accepting "whatever you think is best" as a terminal answer
- producing a spec, plan, or task list before the user has explicitly confirmed
  your restate
- questions framed as "what would be best practice?" instead of "what do you
  actually want?"
- accepting sophistication-signaling answers such as "scalable", "clean", or
  "modern" without probing whether they are what the user actually wants
- three or more rounds without confidence visibly rising
- a confidence number below about 70% with no reason attached
- saving the intent doc before the user has confirmed
- skipping the "Out of scope" line in the restate

## Verification

- an explicit hypothesis with a confidence number was stated in the first turn
- every confidence number below about 70% was accompanied by a one-line reason
- questions were asked one at a time, each with the agent's guess attached
- at least one "what would you actually want if you did not have to justify it?"
  probe ran when the user gave a sophistication-signaling or convention-signaling
  answer
- a concrete restate with Outcome, User, Why now, Success, Constraint, and Out of
  scope was written back to the user
- the user confirmed the restate with an explicit yes
- at the stop point, the agent could predict reactions to the next three
  questions it would ask
- any handoff to a downstream skill was framed in terms of the confirmed intent,
  not the original underspecified ask
