"""Contract tests for bootstrap CLI model-evidence ownership."""

from pathlib import Path


def test_model_evidence_contract_uses_shared_kernel_owner() -> None:
    """Keep feature-neutral CLI evidence protocols pointed at the shared kernel."""
    bootstrap_cli_source = Path("src/fabrica/bootstrap/cli/model_evidence.py").read_text(encoding="utf-8")

    assert "from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence" in bootstrap_cli_source
    assert (
        "from fabrica.features.agent_runtime.application.dtos import (\n"
        "        ModelCostEvidence" not in bootstrap_cli_source
    )
