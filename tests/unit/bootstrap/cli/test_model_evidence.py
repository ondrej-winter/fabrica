"""Contract tests for bootstrap CLI model-evidence ownership."""

from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from fabrica.bootstrap.cli import model_evidence


def test_model_evidence_contract_uses_shared_kernel_owner() -> None:
    """Keep feature-neutral CLI evidence protocols pointed at the shared kernel."""
    bootstrap_cli_source = Path("src/fabrica/bootstrap/cli/model_evidence.py").read_text(encoding="utf-8")

    assert "from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence" in bootstrap_cli_source
    assert (
        "from fabrica.features.agent_runtime.application.dtos import (\n"
        "        ModelCostEvidence" not in bootstrap_cli_source
    )


@dataclass(frozen=True)
class _Result:
    usage_evidence: tuple[object, ...]
    cost_evidence: tuple[object, ...]


def test_writes_requested_model_evidence_through_product_cli_renderer(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def write_report(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(model_evidence, "write_model_evidence_report", write_report)
    result = _Result(usage_evidence=(object(),), cost_evidence=(object(),))
    stdout = StringIO()

    model_evidence.write_requested_model_evidence(
        result,  # ty: ignore[invalid-argument-type]
        include_usage=True,
        include_prices=False,
        stdout=stdout,
    )

    assert captured == {
        "usage_evidence": result.usage_evidence,
        "cost_evidence": result.cost_evidence,
        "stdout": stdout,
        "include_usage": True,
        "include_prices": False,
    }
