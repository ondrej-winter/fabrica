"""Safe runtime diagnostics for commit-message agent-runtime adapters."""

from fabrica.features.developer_workflow.application.dtos import SafeGitStagedChangesMetadataValue


def safe_runtime_metadata(status: str, output_text: str | None) -> dict[str, SafeGitStagedChangesMetadataValue]:
    """Return safe diagnostics for failed runtime results without exposing model output."""
    return {"runtime_status": status, "has_output_text": output_text is not None}
