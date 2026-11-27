"""Slow-operation diagnostics must neither cancel nor change upstream calls."""

import threading
from unittest.mock import Mock

import pytest

from octoprint_mqttforusbrelaycontrol.operations import OperationMonitor


def test_slow_operation_emits_one_warning_while_remaining_active():
    warned = threading.Event()
    release = threading.Event()
    messages = []

    def diagnostic(message):
        messages.append(message)
        warned.set()

    monitor = OperationMonitor(diagnostic, threshold=0.02)

    def upstream():
        with monitor.track("write"):
            with monitor.track("read"):
                assert release.wait(2)

    call = threading.Thread(target=upstream)
    call.start()
    try:
        assert warned.wait(2)
        status = monitor.status()
        assert status["active"] == "write" and status["slow"] is True
        assert status["elapsed"] >= 0.02 and call.is_alive()
        assert "has not been cancelled" in messages[0]
        assert len(messages) == status["slow_count"] == 1
    finally:
        release.set()
        call.join(2)
    assert not call.is_alive()
    status = monitor.status()
    assert status["active"] is None and status["last_kind"] == "write"
    assert status["last_duration"] >= 0.02 and status["slow_count"] == 1


def test_timer_creation_failure_preserves_original_exception(monkeypatch):
    monkeypatch.setattr("threading.Timer", Mock(side_effect=RuntimeError("No timer available")))
    monitor = OperationMonitor(Mock())
    error = OSError("Synthetic upstream failure")
    with pytest.raises(OSError) as raised, monitor.track("read"):
        raise error
    assert raised.value is error
    assert monitor.status()["active"] is None


def test_diagnostic_failure_does_not_escape_timer_callback():
    monitor = OperationMonitor(Mock(side_effect=RuntimeError("Diagnostic unavailable")))
    with monitor.track("read"):
        monitor._warn(monitor.current)
    assert monitor.status()["slow_count"] == 1
