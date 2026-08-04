# Orchestration Patterns

Use these rules when coordinating reviews, subagents, specialist reviewers, or
fresh-context checks.

## Preferred pattern

- The main session owns orchestration.
- Specialist reviewers receive a narrow artifact, contract, and question.
- Reviewers return findings, evidence, and uncertainty without spawning more reviewers.
- The main session integrates findings and decides the next action.

## Anti-patterns

- Specialist reviewer calls another specialist reviewer.
- Reviewer receives the author's full reasoning and is biased toward agreement.
- Reviewer gets an unclear artifact or no acceptance contract.
- Orchestration continues recursively until responsibility is unclear.

## Fresh-context review prompt shape

Provide:

- Artifact under review.
- Contract or acceptance criteria.
- Specific failure modes to look for.
- Required response format.
- Instruction to report only evidence-backed issues and uncertainty.
