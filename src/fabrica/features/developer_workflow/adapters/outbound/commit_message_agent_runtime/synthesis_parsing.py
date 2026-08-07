"""Parsing for final commit-message recommendation model output."""

from fabrica.features.developer_workflow.application.dtos import CommitMessageRecommendation
from fabrica.features.developer_workflow.application.ports import CommitMessageSynthesisError


def parse_synthesis_output(output_text: str) -> CommitMessageRecommendation:
    """Parse terminal-friendly labeled synthesis output into a recommendation DTO."""
    sections = _parse_labeled_sections(output_text)
    try:
        return CommitMessageRecommendation(
            summary=sections["Summary"],
            rationale=sections["Rationale"],
            commit_message=sections["Commit message"],
        )
    except KeyError as err:
        msg = "commit-message synthesis output is missing a required label"
        raise CommitMessageSynthesisError(
            msg,
            metadata={"missing_label": str(err).strip("'")},
        ) from err
    except ValueError as err:
        msg = "commit-message synthesis output contains an empty required section"
        raise CommitMessageSynthesisError(
            msg,
            metadata={"error_type": type(err).__name__},
        ) from err


def _parse_labeled_sections(output_text: str) -> dict[str, str]:
    labels = ("Summary", "Rationale", "Commit message")
    sections: dict[str, list[str]] = {label: [] for label in labels}
    current_label: str | None = None
    for line in output_text.splitlines():
        stripped_line = line.strip()
        matching_label = next((label for label in labels if stripped_line == f"{label}:"), None)
        if matching_label is not None:
            current_label = matching_label
            continue
        if current_label is not None:
            sections[current_label].append(line)
    return {label: _join_section(lines, label=label) for label, lines in sections.items()}


def _join_section(lines: list[str], *, label: str) -> str:
    text = "\n".join(lines).strip()
    if not text:
        msg = "commit-message synthesis output contains an empty required section"
        raise CommitMessageSynthesisError(
            msg,
            metadata={"label": label},
        )
    return text
