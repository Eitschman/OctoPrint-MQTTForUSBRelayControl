"""Command load, expiry and channel pacing without real hardware or sockets."""

import threading
from time import monotonic
from unittest.mock import Mock

import pytest

from octoprint_mqttforusbrelaycontrol.adapter import Observation
from octoprint_mqttforusbrelaycontrol.plugin import validate_settings
from octoprint_mqttforusbrelaycontrol.state_manager import Command, StateManager


def test_publication_and_controls_progress_during_continuous_commands():
    events = []
    published = threading.Event()

    def execute(command):
        events.append("command")
        worker.observe(Observation("a", 1, 0, True, True, sequence=len(events)))
        worker.enqueue(Command(f"next-{len(events)}", 1, 0, True, False))
        worker.request("sync")

    def publish(snapshot):
        events.append("publish")
        published.set()

    def reconcile(reasons):
        events.append("reconcile")
        worker.request("sync")

    worker = StateManager(execute, publish, reconcile, Mock())
    worker.start()
    try:
        assert worker.enqueue(Command("first", 1, 0, True, False))
        assert published.wait(2)
    finally:
        worker.stop()
    assert events[:3] == ["command", "publish", "reconcile"]


def test_expired_commands_are_discarded_before_enqueue_and_dispatch():
    now = [100.0]
    entered, release = threading.Event(), threading.Event()
    execute = Mock()

    def reconcile(reasons):
        entered.set()
        assert release.wait(2)

    worker = StateManager(execute, Mock(), reconcile, Mock(), clock=lambda: now[0])
    worker.start()
    worker.request()
    try:
        assert entered.wait(2)
        assert not worker.enqueue(Command("old", 1, 0, True, False, 95.0))
        assert worker.enqueue(Command("queued", 1, 0, True, False, 100.0))
        now[0] = 105.0
        release.set()
        assert worker.wait_idle()
        execute.assert_not_called()
        assert worker.status()["expired"] == 2
        assert worker.status()["rejected"] == 2
    finally:
        release.set()
        worker.stop()


def test_channel_cooldown_allows_other_channels_and_publication():
    calls = []
    first, second, publication = threading.Event(), threading.Event(), threading.Event()

    def execute(command):
        calls.append((command.relay_id, command.target, monotonic()))
        (first if len(calls) == 1 else second).set()

    worker = StateManager(execute, lambda snapshot: publication.set(), Mock(), Mock())
    worker.configure_commands(5, 0.3)
    worker.start()
    try:
        assert worker.enqueue(Command("a", 1, 0, True, False))
        assert first.wait(2)
        assert worker.enqueue(Command("a", 1, 0, False, False))
        assert worker.enqueue(Command("b", 1, 0, True, False))
        worker.observe(Observation("a", 1, 0, True, True, sequence=1))
        assert second.wait(2) and publication.wait(2)
        assert worker.wait_idle()
        assert [(identity, target) for identity, target, _ in calls] == [
            ("a", True),
            ("b", True),
            ("a", False),
        ]
        assert calls[2][2] - calls[0][2] >= 0.3
    finally:
        worker.stop()


def test_commands_expire_during_cooldown_without_waiting_for_the_full_interval():
    execute = Mock()
    worker = StateManager(execute, Mock(), Mock(), Mock())
    worker.configure_commands(1, 10)
    worker.start()
    try:
        assert worker.enqueue(Command("a", 1, 0, True, False))
        assert worker.wait_idle()
        assert worker.enqueue(Command("a", 1, 0, False, False))
        assert worker.wait_idle(timeout=2)
        execute.assert_called_once()
        assert worker.status()["expired"] == 1
    finally:
        worker.stop()


def test_stop_wakes_a_worker_waiting_for_channel_cooldown():
    worker = StateManager(Mock(), Mock(), Mock(), Mock())
    worker.configure_commands(60, 10)
    worker.start()
    assert worker.enqueue(Command("a", 1, 0, True, False))
    assert worker.wait_idle()
    assert worker.enqueue(Command("a", 1, 0, False, False))
    assert worker.stop(timeout=0.5)


@pytest.mark.parametrize("key", ["command_max_age", "command_min_interval"])
@pytest.mark.parametrize("value", [True, "5", None, float("nan"), float("inf"), 0, -1, 61])
def test_command_limits_reject_invalid_api_and_direct_configuration(key, value):
    with pytest.raises(ValueError, match="finite number"):
        validate_settings({key: value}, "")
    values = {"command_max_age": 5, "command_min_interval": 0.25, key: value}
    worker = StateManager(Mock(), Mock(), Mock(), Mock())
    with pytest.raises(ValueError, match="finite number"):
        worker.configure_commands(values["command_max_age"], values["command_min_interval"])


def test_command_timing_accepts_documented_boundaries():
    for maximum_age, interval in ((1, 0.1), (60, 10)):
        values = {"command_max_age": maximum_age, "command_min_interval": interval}
        assert validate_settings(values, "") == values
        worker = StateManager(Mock(), Mock(), Mock(), Mock())
        worker.configure_commands(maximum_age, interval)
        assert worker.max_command_age == maximum_age
        assert worker.min_command_interval == interval
