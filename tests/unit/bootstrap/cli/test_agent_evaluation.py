"""Tests for public reporting-only mature-agent evaluation CLI composition."""

import json
from io import StringIO
from pathlib import Path

from fabrica.bootstrap.cli import run_cli


def test_public_cli_writes_offline_mature_agent_evaluation_report(tmp_path: Path) -> None:
    report_path = tmp_path / "evaluation.json"
    stdout = StringIO()

    exit_code = run_cli(
        ("agent-evaluate", "--report-path", str(report_path)),
        stdin=StringIO(),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue() == f"Mature-agent evaluation: passed\nScenarios: 6\nReport: {report_path.resolve()}\n"
    assert json.loads(report_path.read_text(encoding="utf-8"))["passed"] is True
