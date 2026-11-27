"""Backend regression tests against the pinned original implementation."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from octoprint_mqttforusbrelaycontrol.adapter import InstanceAdapter
from octoprint_mqttforusbrelaycontrol.mqtt_integration import MQTTIntegration, command_payload
from octoprint_mqttforusbrelaycontrol.relay_registry import RelayRegistry
from octoprint_mqttforusbrelaycontrol.state_manager import Command, StateManager
from tests.upstream import original


@pytest.fixture
def backend():
    plugin = original()
    plugin.on_after_startup()
    registry = RelayRegistry(str(uuid4()))
    observations = []
    diagnostics = []
    epoch = [0]

    def invalidate():
        epoch[0] += 1

    adapter = InstanceAdapter(
        plugin,
        registry,
        observations.append,
        invalidate,
        lambda: epoch[0],
        lambda: {},
        diagnostics.append,
    )
    adapter.install()
    entry = next(iter(registry.entries.values()))
    registry.entries[entry.id] = replace(entry, enabled=True)
    yield SimpleNamespace(
        plugin=plugin,
        registry=registry,
        adapter=adapter,
        observations=observations,
        diagnostics=diagnostics,
        entry=registry.entries[entry.id],
    )
    adapter.uninstall()


@pytest.mark.parametrize("default_state", ["default_on", "default_off"])
@pytest.mark.parametrize("mode", ["active_high", "active_low"])
def test_f12_s03_startup_matches_original_default_write_baseline(default_state, mode):
    baseline = original()
    config = baseline._settings.get(["usbrelay_configurations"])
    config[0].update(default_state=default_state, active_mode=mode)
    baseline._settings.set(["usbrelay_configurations"], config)
    baseline.on_after_startup()
    companion = original(config)
    registry = RelayRegistry(str(uuid4()))
    adapter = InstanceAdapter(companion, registry, Mock(), Mock(), lambda: 0, lambda: {}, Mock())
    adapter.install()
    try:
        companion.on_after_startup()
        assert companion.relays["16c0:05df"].h.writes == baseline.relays["16c0:05df"].h.writes
        assert len(companion.relays) == len(baseline.relays) == 1
    finally:
        adapter.uninstall()


def test_f10_two_channels_preserve_independent_bits(backend):
    b = backend
    config = b.plugin._settings.get(["usbrelay_configurations"])
    config.append(dict(config[0], relaynumber="2", name="Second channel"))
    b.plugin._settings.set(["usbrelay_configurations"], config)
    b.adapter.refresh()
    for identity, entry in list(b.registry.entries.items()):
        b.registry.entries[identity] = replace(entry, enabled=True)
    entries = list(b.registry.entries.values())
    assert len(entries) == 2
    b.adapter.write_verified(entries[0].id, entries[0].generation, True, lambda: True)
    assert entries[0].relay.h.bits == 1
    b.adapter.write_verified(entries[1].id, entries[1].generation, True, lambda: True)
    assert entries[0].relay.h.bits == 3
    b.adapter.write_verified(entries[0].id, entries[0].generation, False, lambda: True)
    assert entries[0].relay.h.bits == 2


@pytest.mark.parametrize("target", [True, False])
@pytest.mark.parametrize("mode", ["active_high", "active_low"])
def test_f01_f02_f08_f09_verified_write(backend, target, mode):
    b = backend
    entry = replace(b.entry, active_mode=mode)
    b.registry.entries[entry.id] = entry
    hardware = entry.relay.h
    writes = len(hardware.writes)
    reads = hardware.reads
    result = b.adapter.write_verified(entry.id, entry.generation, target, lambda: True)
    assert len(hardware.writes) == writes + 1
    assert hardware.reads == reads + 1
    assert result.actual is target and result.outcome == "confirmed"


@pytest.mark.parametrize(
    "write_error,read_error,negative,outcome",
    [
        (None, None, True, "mismatch"),
        (OSError("write"), None, False, "write_failed"),
        (None, OSError("read"), False, "read_failed"),
        (OSError("write"), OSError("read"), False, "read_failed"),
    ],
)
def test_f07_separates_write_read_and_mismatch(backend, write_error, read_error, negative, outcome):
    b = backend
    hardware = b.entry.relay.h
    hardware.write_error, hardware.read_error = write_error, read_error
    hardware.write_result = -1 if negative else 2
    reads = hardware.reads
    result = b.adapter.write_verified(b.entry.id, b.entry.generation, True, lambda: True)
    assert hardware.reads == reads + 1
    assert result.outcome == outcome
    assert (result.write_error is not None) is (write_error is not None)
    assert (result.actual is None) is (read_error is not None)


def test_a04_original_exception_identity_and_postread(backend):
    b = backend
    error = OSError("write")
    b.entry.relay.h.write_error = error
    reads = b.entry.relay.h.reads
    with pytest.raises(OSError) as raised:
        b.entry.relay.state(1, True)
    assert raised.value is error
    assert b.entry.relay.h.reads == reads + 1
    assert b.observations[-1].write_error == "OSError"


def test_a03_a05_observer_failure_preserves_return(backend):
    b = backend
    b.adapter.sink = Mock(side_effect=RuntimeError("observer"))
    assert b.entry.relay.state(1, True) is None
    assert b.diagnostics


def test_a06_getter_none_false_and_all_channels(backend):
    relay = backend.entry.relay
    hardware = relay.h
    writes = len(hardware.writes)
    assert relay.state(1) is False
    assert relay.state(relay=1, on=None) is False
    assert len(hardware.writes) == writes
    assert relay.state(1, on=False) is None
    assert len(hardware.writes) == writes + 1
    assert relay.state(0, True) is None
    assert backend.observations[-1].actual is True


def test_a02_a08_instance_only_idempotent_and_inherited_restore(backend):
    b = backend
    other = original()
    inherited = type(b.plugin).on_api_get
    b.adapter.install()
    assert "on_api_get" not in vars(other)
    assert b.adapter.uninstall()
    assert "on_api_get" not in vars(b.plugin)
    assert b.plugin.on_api_get.__func__ is inherited
    assert b.adapter.uninstall()


def test_a08_foreign_wrapper_is_not_overwritten(backend):
    b = backend
    previous = b.plugin.on_api_get

    def foreign(request):
        return previous(request)

    b.plugin.on_api_get = foreign
    assert b.adapter.uninstall() is False
    assert b.plugin.on_api_get is foreign


def test_original_save_recreates_and_rebinds_without_refresh_default_write(backend):
    b = backend
    old = b.entry.relay
    b.plugin.get_settings_defaults = lambda: {"usbrelay_configurations": []}
    b.plugin.get_settings_version = lambda: None
    configurations = b.plugin._settings.get(["usbrelay_configurations"])
    b.plugin.on_settings_save({"usbrelay_configurations": configurations})
    new = next(iter(b.registry.entries.values()))
    assert new.relay is not old and old.h.closed
    count = len(new.relay.h.writes)
    b.adapter.refresh()
    assert len(new.relay.h.writes) == count
    assert "state" in vars(new.relay)


@pytest.mark.parametrize("payload", [b"TOGGLE", b"on", b"ON ", b"\xff", "", {}, 1])
def test_f03_invalid_payload(payload):
    assert command_payload(payload) is None


def test_f13_retained_and_stale_commands_cannot_enter_worker():
    execute = Mock()
    worker = StateManager(execute, Mock(), Mock(), Mock())
    worker.start()
    assert not worker.enqueue(Command("relay", 1, 0, True, True))
    worker.invalidate()
    assert not worker.enqueue(Command("relay", 1, 0, True, False))
    worker.stop()
    execute.assert_not_called()


def test_blocked_local_hardware_does_not_hang_adapter_teardown(backend):
    import threading

    b = backend
    entered, release = threading.Event(), threading.Event()
    original_write = b.entry.relay.h.send_feature_report

    def blocked_write(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original_write(*args, **kwargs)

    b.entry.relay.h.send_feature_report = blocked_write
    call = threading.Thread(target=lambda: b.entry.relay.state(1, True))
    call.start()
    try:
        assert entered.wait(2)
        assert b.adapter.operations.status()["active"] == "write"
        assert b.adapter.uninstall(timeout=0.01) is False
        assert not b.adapter.active and call.is_alive()
        assert any("restart required" in message for message in b.diagnostics)
    finally:
        release.set()
        call.join(2)
    assert not call.is_alive()
    assert b.adapter.operations.status()["active"] is None


def test_publish_never_queues_and_unsubscribe_is_topic_specific():
    publish, subscribe, unsubscribe = Mock(return_value=True), Mock(), Mock()
    mqtt = MQTTIntegration(
        {"mqtt_publish": publish, "mqtt_subscribe": subscribe, "mqtt_unsubscribe": unsubscribe},
        Mock(),
    )
    mqtt.publish("test/state", "ON")
    publish.assert_called_once_with("test/state", "ON", retained=True, qos=0, allow_queueing=False)
    mqtt.subscribe("test/one", Mock())
    mqtt.subscribe("test/two", Mock())
    mqtt.close()
    assert [call.kwargs for call in unsubscribe.call_args_list] == [
        {"topic": "test/one"},
        {"topic": "test/two"},
    ]
    assert all(len(call.args) == 1 for call in unsubscribe.call_args_list)


def test_n01_local_and_mqtt_transactions_are_serialized(backend):
    import threading

    b = backend
    entered, release = threading.Event(), threading.Event()
    hardware = b.entry.relay.h
    previous = hardware.send_feature_report

    def blocked(message):
        entered.set()
        assert release.wait(3)
        return previous(message)

    hardware.send_feature_report = blocked
    local = threading.Thread(target=lambda: b.entry.relay.state(1, True))
    remote = threading.Thread(
        target=lambda: b.adapter.write_verified(b.entry.id, b.entry.generation, False, lambda: True)
    )
    local.start()
    assert entered.wait(2)
    remote.start()
    release.set()
    local.join(3)
    remote.join(3)
    assert not local.is_alive() and not remote.is_alive()
    assert [item.actual for item in sorted(b.observations, key=lambda item: item.sequence)] == [
        True,
        False,
    ]
    assert hardware.bits == 0


def test_n03_blocked_publisher_does_not_block_local_hardware(backend):
    import threading

    b = backend
    entered, release = threading.Event(), threading.Event()
    revisions = []

    def publish(snapshot):
        entered.set()
        assert release.wait(3)
        revisions.append(snapshot["revision"])

    worker = StateManager(Mock(), publish, Mock(), b.diagnostics.append)
    b.adapter.sink = worker.observe
    b.adapter.epoch = worker.current_epoch
    worker.start()
    try:
        b.entry.relay.state(1, True)
        assert entered.wait(2)
        local = threading.Thread(target=lambda: b.entry.relay.state(1, False))
        local.start()
        local.join(1)
        assert not local.is_alive()
        release.set()
        assert worker.wait_idle()
        assert revisions == sorted(revisions)
        assert worker.snapshots[b.entry.id]["actual"] is False
    finally:
        release.set()
        worker.stop()


def test_queue_overflow_and_invalidation_are_bounded():
    import threading

    entered, release = threading.Event(), threading.Event()

    def reconcile(reasons):
        entered.set()
        assert release.wait(3)

    execute = Mock()
    worker = StateManager(execute, Mock(), reconcile, Mock(), limit=2)
    worker.start()
    worker.request()
    assert entered.wait(2)
    try:
        assert worker.enqueue(Command("a", 1, 0, True, False))
        assert worker.enqueue(Command("a", 1, 0, False, False))
        assert not worker.enqueue(Command("a", 1, 0, True, False))
        assert worker.status()["overflows"] == 1
        worker.invalidate()
        release.set()
        assert worker.wait_idle()
        execute.assert_not_called()
    finally:
        release.set()
        worker.stop()


def test_a05_n05_local_postread_failure_preserves_success(backend):
    b = backend
    b.entry.relay.h.read_error = OSError("read")
    assert b.entry.relay.state(1, True) is None
    assert b.observations[-1].actual is None
    assert b.observations[-1].outcome == "read_failed"


def test_f11_obsolete_or_disabled_entry_never_writes(backend):
    b = backend
    hardware = b.entry.relay.h
    writes = len(hardware.writes)
    assert b.adapter.write_verified(b.entry.id, -1, True, lambda: True) is None
    assert b.adapter.write_verified(b.entry.id, b.entry.generation, True, lambda: False) is None
    b.registry.entries[b.entry.id] = replace(b.entry, enabled=False)
    assert b.adapter.write_verified(b.entry.id, b.entry.generation, True, lambda: True) is None
    assert len(hardware.writes) == writes


def test_n04_pending_reconfiguration_blocks_commands_before_hardware_lock(backend):
    import threading

    b = backend
    b.plugin.get_settings_defaults = lambda: {"usbrelay_configurations": []}
    b.plugin.get_settings_version = lambda: None
    configurations = b.plugin._settings.get(["usbrelay_configurations"])
    hardware = b.entry.relay.h
    writes = len(hardware.writes)
    with b.adapter.lock:
        save = threading.Thread(
            target=lambda: b.plugin.on_settings_save({"usbrelay_configurations": configurations})
        )
        save.start()
        assert b.adapter.reconfiguring.wait(2)
        assert b.adapter.write_verified(b.entry.id, b.entry.generation, True, lambda: True) is None
        assert len(hardware.writes) == writes
    save.join(3)
    assert not save.is_alive() and not b.adapter.reconfiguring.is_set()


def test_n03_out_of_order_observer_delivery_cannot_restore_old_state(backend):
    import threading

    b = backend
    first, release = threading.Event(), threading.Event()
    worker = StateManager(Mock(), Mock(), Mock(), Mock())

    def delayed(observation):
        if observation.sequence == 1:
            first.set()
            assert release.wait(3)
        worker.observe(observation)

    b.adapter.sink = delayed
    local = threading.Thread(target=lambda: b.entry.relay.state(1, True))
    local.start()
    assert first.wait(2)
    b.entry.relay.state(1, False)
    release.set()
    local.join(3)
    assert not local.is_alive()
    assert worker.snapshots[b.entry.id]["actual"] is False


def test_blocked_worker_shutdown_is_bounded_and_reported():
    import threading

    entered, release = threading.Event(), threading.Event()
    diagnostic = Mock()

    def reconcile(reasons):
        entered.set()
        release.wait(3)

    worker = StateManager(Mock(), Mock(), reconcile, diagnostic)
    worker.start()
    worker.request()
    assert entered.wait(2)
    try:
        assert worker.stop(timeout=0.01) is False
        assert "blocked" in diagnostic.call_args.args[0]
    finally:
        release.set()
        assert worker.stop()


@pytest.mark.parametrize("path", ["save", "refresh"])
def test_review_replaced_relays_leave_no_adapter_references(path):
    import gc
    import weakref

    plugin = original()
    plugin.on_after_startup()
    plugin.get_settings_defaults = lambda: {"usbrelay_configurations": []}
    plugin.get_settings_version = lambda: None
    registry = RelayRegistry(str(uuid4()))
    adapter = InstanceAdapter(plugin, registry, Mock(), Mock(), lambda: 0, lambda: {}, Mock())
    adapter.install()
    try:
        for _ in range(20):
            old = plugin.relays["16c0:05df"]
            reference = weakref.ref(old)
            atexit = type(old).__init__.__globals__["atexit"]
            configuration = plugin._settings.get(["usbrelay_configurations"])
            if path == "save":
                plugin.on_settings_save({"usbrelay_configurations": configuration})
            else:
                old.cleanup()
                plugin.relays = {}
                plugin.on_after_startup.__wrapped__()
                adapter.refresh()
            assert "state" not in vars(old)
            # Upstream atexit registration independently retains cleanup callbacks.
            # Clear only this synthetic registry to isolate companion references.
            atexit.reset_mock()
            del old
            gc.collect()
            assert reference() is None
            assert len(adapter.manifest) == 5
    finally:
        adapter.uninstall()


def test_review_retired_foreign_wrapper_is_preserved_but_companion_becomes_inert(backend):
    b = backend
    old = b.entry.relay
    previous = old.state

    def foreign(*args, **kwargs):
        return previous(*args, **kwargs)

    old.state = foreign
    b.plugin.get_settings_defaults = lambda: {"usbrelay_configurations": []}
    b.plugin.get_settings_version = lambda: None
    b.plugin.on_settings_save(
        {"usbrelay_configurations": b.plugin._settings.get(["usbrelay_configurations"])}
    )
    assert old.state is foreign and len(b.adapter.manifest) == 5
    count = len(b.observations)
    foreign(1)
    assert len(b.observations) == count
    assert any("ownership changed" in message for message in b.diagnostics)
    assert b.adapter.uninstall() is False


def test_review_failed_original_reconstruction_prunes_retired_bindings(backend):
    b = backend
    old = b.entry.relay
    b.plugin.get_settings_defaults = lambda: {"usbrelay_configurations": []}
    b.plugin.get_settings_version = lambda: None
    with pytest.raises(TypeError):
        b.plugin.on_settings_save({"usbrelay_configurations": None})
    assert not b.registry.entries and "state" not in vars(old)
    assert len(b.adapter.manifest) == 4
