"""Safe runtime diagnostics for commit-message agent-runtime adapters."""

from collections.abc import Sequence

from fabrica.features.agent_runtime.application.dtos import RuntimeObservation
from fabrica.features.developer_workflow.application.dtos import SafeGitStagedChangesMetadataValue

_SAFE_RUNTIME_OBSERVATION_METADATA_KEYS = frozenset(
    {
        "transport_status",
        "http_status",
        "category",
        "error_type",
        "response_shape",
    }
)


def safe_runtime_metadata(
    status: str,
    output_text: str | None,
    observations: Sequence[RuntimeObservation] = (),
) -> dict[str, SafeGitStagedChangesMetadataValue]:
    """Return safe diagnostics for failed runtime results without exposing model output."""
    metadata: dict[str, SafeGitStagedChangesMetadataValue] = {
        "runtime_status": status,
        "has_output_text": output_text is not None,
    }
    first_observation = observations[0] if observations else None
    if first_observation is not None:
        metadata.update(_safe_runtime_observation_metadata(first_observation))
    return metadata


def _safe_runtime_observation_metadata(
    observation: RuntimeObservation,
) -> dict[str, SafeGitStagedChangesMetadataValue]:
    return {
        f"runtime_{key}": value
        for key, value in observation.metadata.items()
        if key in _SAFE_RUNTIME_OBSERVATION_METADATA_KEYS
    }
