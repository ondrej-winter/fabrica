"""Tests for process-group subprocess construction."""

import subprocess
from dataclasses import dataclass

import pytest

from fabrica.adapters.outbound.process_group_subprocess import process


@dataclass
class _FakeProcess:
    """Minimal process returned by the patched Popen boundary."""

    outcomes: list[tuple[str, str]]


def test_open_process_delegates_to_subprocess_popen(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_process = _FakeProcess(outcomes=[])
    observed_kwargs: dict[str, object] = {}

    def popen(*_args: object, **kwargs: object) -> _FakeProcess:
        observed_kwargs.update(kwargs)
        return fake_process

    monkeypatch.setattr(process.subprocess, "Popen", popen)

    assert (
        process.open_process(
            ("tool", "--version"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=None,
            env={"PATH": "/bin"},
            shell=False,
            text=True,
            start_new_session=True,
        )
        is fake_process
    )
    assert observed_kwargs == {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "cwd": None,
        "env": {"PATH": "/bin"},
        "shell": False,
        "text": True,
        "start_new_session": True,
    }
