"""Failing disposable services must report their startup error without a blind timeout."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.services import broker


@pytest.mark.parametrize("exit_code", [0, 3])
@pytest.mark.parametrize("override_directory", [False, True])
def test_broker_reports_early_exit_and_reaps_process(
    tmp_path, monkeypatch, exit_code, override_directory
):
    process = Mock(returncode=exit_code)
    process.poll.return_value = exit_code
    config_root = tmp_path / "broker"
    if override_directory:
        config_root = tmp_path / "allowed-configurations"
        config_root.mkdir()
        monkeypatch.setenv("MOSQUITTO_CONFIG_DIRECTORY", str(config_root))
    else:
        monkeypatch.delenv("MOSQUITTO_CONFIG_DIRECTORY", raising=False)
    sentinel = config_root / "unrelated.conf"
    config_root.mkdir(exist_ok=True)
    sentinel.write_text("Preserve unrelated files")

    def start_process(command, *, stdout, stderr):
        configuration = Path(command[2])
        assert configuration.parent.parent == config_root
        assert "127.0.0.1" in configuration.read_text()
        stdout.write("Synthetic broker configuration failure\n")
        stdout.flush()
        return process

    monkeypatch.setenv("MOSQUITTO_BINARY", "synthetic-broker")
    monkeypatch.setattr(subprocess, "Popen", start_process)
    with pytest.raises(RuntimeError, match="Synthetic broker configuration failure"):
        with broker(tmp_path / "broker"):
            pytest.fail("An exited broker must not be considered ready")
    process.wait.assert_called_once_with(timeout=10)
    assert sentinel.read_text() == "Preserve unrelated files"
    assert not list(config_root.glob("relay-broker-*"))
