"""Failing disposable services must report their startup error without a blind timeout."""

import subprocess
from unittest.mock import Mock

import pytest

from tests.services import broker


@pytest.mark.parametrize("exit_code", [0, 3])
def test_broker_reports_early_exit_and_reaps_process(tmp_path, monkeypatch, exit_code):
    process = Mock(returncode=exit_code)
    process.poll.return_value = exit_code

    def start_process(command, *, stdout, stderr):
        stdout.write("Synthetic broker configuration failure\n")
        stdout.flush()
        return process

    monkeypatch.setenv("MOSQUITTO_BINARY", "synthetic-broker")
    monkeypatch.setattr(subprocess, "Popen", start_process)
    with pytest.raises(RuntimeError, match="Synthetic broker configuration failure"):
        with broker(tmp_path / "broker"):
            pytest.fail("An exited broker must not be considered ready")
    process.wait.assert_called_once_with(timeout=10)
