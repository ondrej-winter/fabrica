"""Tests for deterministic mature-agent evaluation report output."""

import json
from pathlib import Path

from fabrica.features.agent_evaluation.adapters.outbound import JsonEvaluationReportWriter
from fabrica.features.agent_evaluation.application import EvaluateMatureAgentCorpus
from fabrica.features.agent_evaluation.application.fixtures import mature_agent_corpus


def test_writer_emits_a_stable_versioned_json_report(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"

    path = JsonEvaluationReportWriter().write(EvaluateMatureAgentCorpus(mature_agent_corpus()).execute(), destination)

    assert path == destination.resolve()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "corpus_version": 1,
        "passed": True,
        "results": [
            {
                "assertions": [
                    "normalized session evidence is present",
                    "required transcript, tool, and state events are present",
                    "prohibited host and provider capture fragments are absent",
                ],
                "failures": [],
                "passed": True,
                "scenario_id": "approved-scoped-edit-validation",
            },
            {
                "assertions": [
                    "normalized session evidence is present",
                    "required transcript, tool, and state events are present",
                    "prohibited host and provider capture fragments are absent",
                ],
                "failures": [],
                "passed": True,
                "scenario_id": "denied-approval-recovery",
            },
            {
                "assertions": [
                    "normalized session evidence is present",
                    "required transcript, tool, and state events are present",
                    "prohibited host and provider capture fragments are absent",
                ],
                "failures": [],
                "passed": True,
                "scenario_id": "fingerprint-mismatch-replan",
            },
            {
                "assertions": [
                    "normalized session evidence is present",
                    "required transcript, tool, and state events are present",
                    "prohibited host and provider capture fragments are absent",
                ],
                "failures": [],
                "passed": True,
                "scenario_id": "inspect-only-success",
            },
            {
                "assertions": [
                    "normalized session evidence is present",
                    "required transcript, tool, and state events are present",
                    "prohibited host and provider capture fragments are absent",
                ],
                "failures": [],
                "passed": True,
                "scenario_id": "interruption-safe-boundary-resume",
            },
            {
                "assertions": [
                    "normalized session evidence is present",
                    "required transcript, tool, and state events are present",
                    "prohibited host and provider capture fragments are absent",
                ],
                "failures": [],
                "passed": True,
                "scenario_id": "secret-capture-exclusions",
            },
        ],
        "schema_version": 1,
    }
