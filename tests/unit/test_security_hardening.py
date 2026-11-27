"""Failure diagnostics must remain observable without disabling the relay worker."""

import copy
import logging
import threading
from unittest.mock import Mock

import pytest

from octoprint_mqttforusbrelaycontrol.adapter import InstanceAdapter
from octoprint_mqttforusbrelaycontrol.operations import OperationMonitor
from octoprint_mqttforusbrelaycontrol.state_manager import StateManager
from tools.check_security_scan import validate_scan

SECRET = "synthetic-sensitive-error-content"


def test_worker_survives_failed_operation_diagnostic_and_notification_callbacks(caplog):
    recovered = threading.Event()

    def reconcile(reasons):
        if "fail" in reasons:
            raise RuntimeError(SECRET)
        recovered.set()

    worker = StateManager(Mock(), Mock(), reconcile, Mock(side_effect=ValueError(SECRET)),
                          changed=Mock(side_effect=OSError(SECRET)))
    with caplog.at_level(logging.WARNING):
        worker.start()
        try:
            worker.request("fail")
            assert worker.wait_idle()
            worker.request("recover")
            assert recovered.wait(2)
            assert worker.wait_idle()
        finally:
            assert worker.stop()
    assert "Worker diagnostic callback failed: ValueError" in caplog.text
    assert "Worker notification callback failed: OSError" in caplog.text
    assert SECRET not in caplog.text
    assert worker.status()["active"] is None
    assert worker.status()["last_duration"] is not None


def test_adapter_diagnostic_failure_is_logged_without_exposing_exception_content(caplog):
    adapter = InstanceAdapter(Mock(), Mock(), Mock(), Mock(), Mock(), Mock(),
                              Mock(side_effect=ValueError(SECRET)))
    with caplog.at_level(logging.WARNING):
        adapter._diagnose("State observer failed", OSError(SECRET))
    assert "Diagnostic callback failed: ValueError" in caplog.text
    assert SECRET not in caplog.text


def test_hardware_warning_callback_failure_is_logged_without_interrupting_the_operation(caplog):
    monitor = OperationMonitor(Mock(side_effect=ValueError(SECRET)))
    with caplog.at_level(logging.WARNING), monitor.track("read"):
        monitor._warn(monitor.current)
        assert monitor.status()["active"] == "read"
    assert "Hardware diagnostic callback failed: ValueError" in caplog.text
    assert SECRET not in caplog.text
    assert monitor.status()["active"] is None


def scan(path):
    return {"errors": [], "results": [], "metrics": {str(path): {"loc": 1}, "_totals": {"loc": 1, "skipped_tests": 0}}}


@pytest.mark.parametrize("problem", ["missing-file", "scanner-error", "finding", "empty-scan", "suppressed-check"])
def test_static_scan_cannot_pass_with_errors_findings_or_missing_runtime_files(tmp_path, problem):
    path = (tmp_path / "runtime.py").resolve()
    report = scan(path)
    if problem == "missing-file":
        report["metrics"].pop(str(path))
    elif problem == "scanner-error":
        report["errors"] = [{"reason": "Could not parse file"}]
    elif problem == "finding":
        report["results"] = [{"test_id": "B101"}]
    elif problem == "empty-scan":
        report["metrics"]["_totals"]["loc"] = 0
    else:
        report["metrics"]["_totals"]["skipped_tests"] = 1
    with pytest.raises(ValueError):
        validate_scan(report, {path})


def test_static_scan_accepts_complete_clean_coverage(tmp_path):
    path = (tmp_path / "runtime.py").resolve()
    validate_scan(copy.deepcopy(scan(path)), {path})
