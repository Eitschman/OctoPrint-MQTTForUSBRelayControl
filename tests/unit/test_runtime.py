"""Full companion runtime with actual pinned helper and original relay methods."""

import copy
import json
import logging
import threading
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from octoprint_mqttforusbrelaycontrol.constants import DEFAULTS
from octoprint_mqttforusbrelaycontrol.device_identity import DeviceIdentityCache
from octoprint_mqttforusbrelaycontrol.lifecycle import RelayRuntime
from octoprint_mqttforusbrelaycontrol.relay_registry import RelayRegistry
from tests.upstream import Settings, mqtt, original


class Manager:
    def __init__(self, usb, transport):
        self.infos = {
            "usbrelaycontrol": SimpleNamespace(implementation=usb, version="1.0.0"),
            "mqtt": SimpleNamespace(implementation=transport, version="0.8.20"),
        }
        self.receivers = []

    def register_message_receiver(self, callback):
        self.receivers.append(callback)

    def unregister_message_receiver(self, callback):
        self.receivers.remove(callback)

    def get_plugin_info(self, key, require_enabled=True):
        return self.infos.get(key)

    def get_helpers(self, key, *names):
        return {name: getattr(self.infos[key].implementation, name) for name in names}


@pytest.fixture
def running(tmp_path):
    usb = original()
    usb.on_after_startup()
    transport = mqtt()
    registry = RelayRegistry(str(uuid4()))
    registry.rebuild(usb)
    identity = next(iter(registry.entries))
    config = copy.deepcopy(DEFAULTS)
    config.update(
        instance_uuid=registry.instance_uuid,
        integration_enabled=True,
        relays={identity: {"enabled": True}},
    )
    manager = Manager(usb, transport)
    runtime = RelayRuntime(
        manager, Settings(config), tmp_path, logging.getLogger("test.runtime"), Mock()
    )
    runtime.start()
    assert runtime.worker.wait_idle()
    runtime.on_plugin_message("mqtt", {"connected": True})
    assert runtime.worker.wait_idle()
    assert runtime.ready, runtime.status()
    yield SimpleNamespace(
        runtime=runtime, usb=usb, mqtt=transport, manager=manager, identity=identity
    )
    runtime.stop()


def deliver(running, payload, retained=False, suffix="set"):
    topic = running.runtime.topics[running.identity][suffix]
    receiver = running.runtime.transport.subscriptions[topic][0]
    receiver(topic, payload, retained=retained, qos=0)
    assert running.runtime.worker.wait_idle()


def test_f01_f06_command_roundtrip_and_plugin_status(running):
    r = running
    entry = r.runtime.registry.entries[r.identity]
    hardware = entry.relay.h
    writes, reads = len(hardware.writes), hardware.reads
    deliver(r, b"ON")
    assert len(hardware.writes) == writes + 1 and hardware.reads == reads + 1
    snapshot = r.runtime.status()["relays"][0]["snapshot"]
    assert snapshot["actual"] is True and snapshot["target"] is True
    r.mqtt._mqtt.publish.assert_any_call(
        r.runtime.topics[r.identity]["state"], payload="ON", qos=0, retain=True
    )


def test_n02_f04_f24_repeated_absolute_commands_and_noncommand_topics(running):
    r = running
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes, reads = len(hardware.writes), hardware.reads
    receiver = r.runtime.transport.subscriptions[r.runtime.topics[r.identity]["set"]][0]
    receiver(r.runtime.topics[r.identity]["state"], b"ON", retained=False)
    receiver("unknown/channel/set", b"ON", retained=False)
    assert len(hardware.writes) == writes
    for payload in (b"ON", b"ON", b"OFF", b"OFF"):
        deliver(r, payload)
    assert len(hardware.writes) == writes + 4 and hardware.reads == reads + 4
    assert hardware.bits == 0


@pytest.mark.parametrize("retained", [True, None, 0, "false"])
def test_f13_missing_or_retained_metadata_is_rejected(running, retained):
    r = running
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes = len(hardware.writes)
    deliver(r, b"ON", retained=retained)
    assert len(hardware.writes) == writes


def test_l02_reconnect_reads_actual_without_offline_history(running):
    r = running
    hardware = r.runtime.registry.entries[r.identity].relay.h
    r.runtime.on_plugin_message("mqtt", {"connected": False})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.reset_mock()
    hardware.bits = 1
    r.runtime.on_plugin_message("mqtt", {"connected": True})
    assert r.runtime.worker.wait_idle()
    states = [
        call.kwargs["payload"]
        for call in r.mqtt._mqtt.publish.call_args_list
        if call.args[0].endswith("/state")
    ]
    assert states == ["ON"]
    assert not r.mqtt._mqtt_publish_queue


@pytest.mark.parametrize("failure", ["write_error", "read_error"])
def test_f07_l04_failed_verification_marks_offline_without_inventing_state(running, failure):
    r = running
    hardware = r.runtime.registry.entries[r.identity].relay.h
    setattr(hardware, failure, OSError("Synthetic failure"))
    r.mqtt._mqtt.publish.reset_mock()
    deliver(r, b"ON")
    calls = r.mqtt._mqtt.publish.call_args_list
    assert any(
        call.args[0].endswith("/availability") and call.kwargs["payload"] == "offline"
        for call in calls
    )
    snapshot = r.runtime.status()["relays"][0]["snapshot"]
    assert snapshot[failure] == "OSError" and snapshot["target"] is True
    if failure == "read_error":
        assert snapshot["actual"] is None
        assert not any(call.args[0].endswith("/state") for call in calls)
    else:
        assert snapshot["actual"] is False


def test_l03_lwt_off_gates_commands_without_modifying_mqtt(running):
    r = running
    r.mqtt._settings.set(["publish", "lwActive"], False)
    expected = r.mqtt._settings.get([])
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert not r.runtime.ready and "Last Will" in r.runtime.last_error
    assert r.mqtt._settings.get([]) == expected
    assert not r.runtime.transport.subscriptions


def test_l07_retained_cannot_override_authoritative_disconnect(running):
    r = running
    r.runtime.on_plugin_message("mqtt", {"connected": False})
    r.runtime._bootstrap("test/mqtt", b"connected", retained=True)
    assert r.runtime.connected is False


def test_f16_birth_is_read_only(running):
    r = running
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes, reads = len(hardware.writes), hardware.reads
    r.runtime._birth("homeassistant/status", b"online", retained=False)
    assert r.runtime.worker.wait_idle()
    assert len(hardware.writes) == writes and hardware.reads > reads


def test_l05_l06_reactivation_rebinds_replaced_plugin_instances(running):
    r = running
    previous = r.runtime.adapter
    old_method = previous.original.relays["16c0:05df"].state
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    assert not previous.active and r.runtime.adapter is None
    replacement = original()
    replacement.on_after_startup()
    r.manager.infos["usbrelaycontrol"].implementation = replacement
    r.runtime.on_event("plugin_pluginmanager_enable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready and r.runtime.adapter.original is replacement
    before = r.runtime.worker.revision
    old_method(1)
    assert r.runtime.worker.revision == before


def test_settings_event_without_change_does_not_read(running):
    hardware = running.runtime.registry.entries[running.identity].relay.h
    reads = hardware.reads
    running.runtime.settings_updated()
    assert running.runtime.worker.wait_idle()
    assert hardware.reads == reads


@pytest.mark.parametrize(
    ("base_topic", "mqtt_prefix", "device_name", "expected_name"),
    [
        ("octoPrint/", "", "", "octoPrint"),
        ("printers/workshop/", "", "", "printers/workshop"),
        ("printers/workshop", "", "", "printers/workshop"),
        ("octoPrint/", "custom/relay", "", "octoPrint"),
        ("octoPrint/", "", "Workshop printer", "Workshop printer"),
    ],
)
def test_device_name_defaults_to_upstream_base_topic(
    running, base_topic, mqtt_prefix, device_name, expected_name
):
    r = running
    r.mqtt._settings.set(["publish", "baseTopic"], base_topic)
    r.runtime.settings.set(["mqtt_prefix"], mqtt_prefix)
    r.runtime.settings.set(["device_name"], device_name)
    r.mqtt._mqtt.publish.reset_mock()
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready
    payload = next(iter(r.runtime.configurations.values()))
    assert payload["device"]["name"] == expected_name
    assert r.runtime.settings.get(["device_name"]) == device_name
    assert payload["unique_id"] == r.identity
    published = [
        json.loads(call.kwargs["payload"])
        for call in r.mqtt._mqtt.publish.call_args_list
        if call.args[0].endswith("/config") and call.kwargs["payload"]
    ]
    assert len(published) == 1
    assert published[0]["device"]["name"] == expected_name


def test_device_name_follows_base_topic_changes_and_can_restore_default(running):
    r = running
    identifiers = next(iter(r.runtime.configurations.values()))["device"]["identifiers"]
    for base, override, expected in (
        ("first/", "", "first"),
        ("second/", "Custom name", "Custom name"),
        ("third/", "Custom name", "Custom name"),
        ("third/", "", "third"),
    ):
        r.mqtt._settings.set(["publish", "baseTopic"], base)
        r.runtime.settings.set(["device_name"], override)
        r.runtime.settings_updated()
        assert r.runtime.worker.wait_idle()
        assert r.runtime.ready
        payload = next(iter(r.runtime.configurations.values()))
        assert payload["device"] == {"name": expected, "identifiers": identifiers}
        assert payload["unique_id"] == r.identity


def add_discovery_plugin(running, identifier="ABC123", name="OctoPrint"):
    settings = Settings({"node_id": identifier, "node_name": name})
    settings.save = Mock()
    running.manager.infos["homeassistant"] = SimpleNamespace(
        implementation=SimpleNamespace(_settings=settings), version="synthetic"
    )
    return settings


@pytest.mark.parametrize("identifier", ["ABC123", "abcdef0123456789abcdef0123456789"])
def test_default_grouping_uses_existing_discovery_identity_without_foreign_writes(
    running, identifier
):
    r = running
    settings = add_discovery_plugin(r, identifier)
    before = settings.get([])
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert next(iter(r.runtime.configurations.values()))["device"] == {
        "identifiers": [identifier],
        "name": "OctoPrint",
    }
    assert r.runtime.status()["device_source"] == "octoprint"
    assert r.runtime.status()["device_identifier"] == identifier
    assert settings.get([]) == before
    settings.save.assert_not_called()


@pytest.mark.parametrize("use_existing", [False, True])
def test_custom_device_identifier_overrides_automatic_grouping(running, use_existing):
    r = running
    add_discovery_plugin(r)
    r.runtime.settings.set(["use_octoprint_device"], use_existing)
    r.runtime.settings.set(["device_identifier"], "Custom-device-ID")
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert next(iter(r.runtime.configurations.values()))["device"] == {
        "identifiers": ["Custom-device-ID"]
    }
    assert r.runtime.status()["device_source"] == "custom"
    r.runtime.settings.set(["device_name"], "My device")
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert next(iter(r.runtime.configurations.values()))["device"]["name"] == "My device"


def test_separate_device_option_preserves_original_device_identity(running):
    r = running
    separate = next(iter(r.runtime.configurations.values()))["device"]
    add_discovery_plugin(r)
    r.runtime.settings.set(["use_octoprint_device"], False)
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert next(iter(r.runtime.configurations.values()))["device"] == separate


def test_grouping_changes_republish_without_changing_entity_identity_or_topics(running):
    r = running
    settings = add_discovery_plugin(r)
    original_topics = copy.deepcopy(r.runtime.topics)
    config_topic = next(iter(r.runtime.configurations))
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes = len(hardware.writes)
    for identifier, name in (("ABC123", "OctoPrint"), ("def456", "Renamed printer")):
        settings.set(["node_id"], identifier)
        settings.set(["node_name"], name)
        r.mqtt._mqtt.publish.reset_mock()
        r.runtime.on_event("SettingsUpdated", {})
        assert r.runtime.worker.wait_idle()
        payload = r.runtime.configurations[config_topic]
        assert payload["device"] == {"identifiers": [identifier], "name": name}
        assert payload["unique_id"] == r.identity
        assert r.runtime.topics == original_topics
        published = [
            call for call in r.mqtt._mqtt.publish.call_args_list if call.args[0].endswith("/config")
        ]
        assert len(published) == 1 and published[0].args[0] == config_topic
        assert json.loads(published[0].kwargs["payload"]) == payload
        assert not r.runtime.ledger.tombstones
    assert len(hardware.writes) == writes


@pytest.mark.parametrize("event", ["disable", "uninstall"])
def test_optional_discovery_lifecycle_switches_grouping_without_unbinding_relays(running, event):
    r = running
    add_discovery_plugin(r)
    adapter = r.runtime.adapter
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.status()["device_source"] == "octoprint"
    r.runtime.on_event(f"plugin_pluginmanager_{event}_plugin", {"id": "homeassistant"})
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready and r.runtime.adapter is adapter
    assert r.runtime.status()["device_source"] == "separate"
    r.runtime.on_event("plugin_pluginmanager_enable_plugin", {"id": "homeassistant"})
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready and r.runtime.adapter is adapter
    assert r.runtime.status()["device_source"] == "octoprint"


@pytest.mark.parametrize("identifier", [None, "", 17, "\n", " x", "x" * 129])
def test_invalid_optional_identity_falls_back_to_separate_device(running, identifier):
    r = running
    before = next(iter(r.runtime.configurations.values()))["device"]
    add_discovery_plugin(r, identifier)
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready
    assert next(iter(r.runtime.configurations.values()))["device"] == before


@pytest.mark.parametrize("failure", ["settings", "lookup", "implementation", "getter"])
def test_optional_identity_read_failure_does_not_disable_relay_integration(running, failure):
    r = running
    settings = add_discovery_plugin(r)
    if failure == "getter":
        settings.get = Mock(side_effect=RuntimeError("Synthetic optional settings failure"))
    elif failure == "settings":
        r.manager.infos["homeassistant"].implementation = object()
    elif failure == "implementation":
        r.manager.infos["homeassistant"].implementation = None
    else:
        lookup = r.manager.get_plugin_info

        def get_plugin_info(key, **kwargs):
            if key == "homeassistant":
                raise RuntimeError("Synthetic optional lookup failure")
            return lookup(key, **kwargs)

        r.manager.get_plugin_info = get_plugin_info
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready and r.runtime.status()["device_source"] == "separate"


def test_shared_device_without_valid_name_preserves_target_name(running):
    r = running
    add_discovery_plugin(r, name="\x00")
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready
    assert next(iter(r.runtime.configurations.values()))["device"] == {"identifiers": ["ABC123"]}


@pytest.mark.parametrize("failure", ["getter", "lookup", "invalid"])
def test_transient_identity_failure_preserves_confirmed_assignment_and_recovers(running, failure):
    r = running
    settings = add_discovery_plugin(r)
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    before = copy.deepcopy(r.runtime.configurations)
    hardware = r.runtime.registry.entries[r.identity].relay.h
    reads, writes = hardware.reads, len(hardware.writes)
    getter, lookup = settings.get, r.manager.get_plugin_info
    if failure == "getter":
        settings.get = Mock(side_effect=RuntimeError("Temporary read failure"))
    elif failure == "lookup":

        def unavailable(key, **kwargs):
            if key == "homeassistant":
                raise RuntimeError("Temporary lookup failure")
            return lookup(key, **kwargs)

        r.manager.get_plugin_info = unavailable
    else:
        settings.set(["node_id"], "")
    r.runtime.notify.reset_mock()
    r.mqtt._mqtt.publish.reset_mock()
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.configurations == before
    assert r.runtime.status()["device_identity_cached"] is True
    assert r.runtime.notify.call_args.args[0]["device_warning"] == "cached"
    assert hardware.reads == reads and len(hardware.writes) == writes
    r.mqtt._mqtt.publish.assert_not_called()
    settings.get, r.manager.get_plugin_info = getter, lookup
    settings.set(["node_id"], "New-ID")
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.status()["device_identifier"] == "New-ID"
    assert r.runtime.status()["device_warning"] is None
    assert DeviceIdentityCache(r.runtime.data_folder).value["node_id"] == "New-ID"


def test_restart_uses_saved_identity_only_during_transient_source_failure(running):
    r = running
    settings = add_discovery_plugin(r)
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    r.runtime.stop()
    settings.get = Mock(side_effect=RuntimeError("Temporary startup read failure"))
    runtime = RelayRuntime(
        r.manager, r.runtime.settings, r.runtime.data_folder, r.runtime.logger, Mock()
    )
    runtime.start()
    try:
        assert runtime.worker.wait_idle()
        runtime.on_plugin_message("mqtt", {"connected": True})
        assert runtime.worker.wait_idle()
        assert runtime.ready and runtime.status()["device_identity_cached"]
        assert runtime.status()["device_identifier"] == "ABC123"
        for key, value, expected in (
            ("device_identifier", "Custom-ID", "custom"),
            ("device_identifier", "", "octoprint"),
            ("use_octoprint_device", False, "separate"),
            ("use_octoprint_device", True, "octoprint"),
        ):
            runtime.settings.set([key], value)
            runtime.settings_updated()
            assert runtime.worker.wait_idle()
            assert runtime.status()["device_source"] == expected
        r.manager.infos.pop("homeassistant")
        runtime.settings_updated()
        assert runtime.worker.wait_idle()
        assert runtime.status()["device_source"] == "separate"
        assert runtime.status()["device_warning"] is None
    finally:
        runtime.stop()


def test_identity_cache_write_failure_is_visible_without_blocking_integration(running, monkeypatch):
    r = running
    add_discovery_plugin(r)
    monkeypatch.setattr(r.runtime.device_cache, "remember", Mock(return_value=False))
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready and r.runtime.status()["device_identifier"] == "ABC123"
    assert r.runtime.status()["device_warning"] == "cache_write_failed"


def test_command_expiry_is_rechecked_after_waiting_for_hardware_lock(running):
    r = running
    adapter = r.runtime.adapter
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes = len(hardware.writes)
    entered = threading.Event()
    original_write = adapter.write_verified
    now = [monotonic()]
    r.runtime.worker.clock = lambda: now[0]

    def waiting_write(*args, **kwargs):
        entered.set()
        return original_write(*args, **kwargs)

    adapter.write_verified = waiting_write
    with adapter.lock:
        topic = r.runtime.topics[r.identity]["set"]
        receiver = r.runtime.transport.subscriptions[topic][0]
        receiver(topic, b"ON", retained=False)
        assert entered.wait(2)
        assert r.runtime.status()["worker"]["active"] == "command"
        now[0] += 6
    assert r.runtime.worker.wait_idle()
    assert len(hardware.writes) == writes
    assert r.runtime.status()["worker"]["expired"] == 1


def test_unchanged_settings_save_restores_readiness_after_invalidation(running):
    r = running
    r.runtime.invalidate()
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert r.runtime.ready and r.runtime.status()["relays"][0]["snapshot"] is not None
    deliver(r, b"ON")
    assert r.runtime.status()["relays"][0]["snapshot"]["actual"] is True


def test_failed_adapter_restoration_requires_restart_before_rebinding(running, monkeypatch):
    r = running
    adapter = r.runtime.adapter
    original_uninstall = adapter.uninstall
    monkeypatch.setattr(adapter, "uninstall", Mock(return_value=False))
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    assert r.runtime.status()["restart_required"] is True
    assert not r.runtime.ready
    r.runtime.on_event("plugin_pluginmanager_enable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    assert not r.runtime.ready and r.runtime.adapter is None
    assert "restart required" in r.runtime.last_error
    original_uninstall()


def test_slow_local_hardware_call_pushes_live_warning_without_cancellation(running):
    r = running
    monitor = r.runtime.adapter.operations
    monitor.threshold = 0.02
    hardware = r.runtime.registry.entries[r.identity].relay.h
    original_read = hardware.get_feature_report
    entered, release, warned = threading.Event(), threading.Event(), threading.Event()
    updates = []

    def blocked_read(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original_read(*args, **kwargs)

    def notify(status):
        updates.append(status)
        if status["hardware"].get("slow"):
            warned.set()

    hardware.get_feature_report = blocked_read
    r.runtime.notify = notify
    call = threading.Thread(target=lambda: r.runtime.registry.entries[r.identity].relay.state(1))
    call.start()
    try:
        assert entered.wait(2) and warned.wait(2)
        assert call.is_alive()
        warning = next(status for status in updates if status["hardware"]["slow"])
        assert warning["hardware"]["active"] == "read"
        assert warning["hardware"]["elapsed"] >= 0.02
        assert "has not been cancelled" in warning["last_error"]
    finally:
        release.set()
        call.join(2)
        hardware.get_feature_report = original_read
    assert not call.is_alive() and r.runtime.worker.wait_idle()
    assert monitor.status()["active"] is None and monitor.status()["slow_count"] == 1


def test_corrupt_custom_device_identifier_blocks_discovery_submission(running):
    r = running
    r.runtime.settings.set(["device_identifier"], "\x00")
    r.mqtt._mqtt.publish.reset_mock()
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert not r.runtime.ready and "Device identifier" in r.runtime.last_error
    assert not any(call.args[0].endswith("/config") for call in r.mqtt._mqtt.publish.call_args_list)


def test_shared_name_can_be_overridden_without_copying_other_device_metadata(running):
    r = running
    add_discovery_plugin(r)
    r.runtime.settings.set(["device_name"], "My printer")
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert next(iter(r.runtime.configurations.values()))["device"] == {
        "identifiers": ["ABC123"],
        "name": "My printer",
    }


def test_d05_clone_offline_detaches_old_topics_without_deleting(running):
    r = running
    old_identity = r.runtime.registry.instance_uuid
    with pytest.raises(ValueError):
        r.runtime.clone_identity(True)
    r.runtime.on_plugin_message("mqtt", {"connected": False})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.reset_mock()
    new_identity = r.runtime.clone_identity(True)
    assert r.runtime.worker.wait_idle()
    assert new_identity != old_identity
    assert r.runtime.registry.instance_uuid == new_identity
    r.mqtt._mqtt.publish.assert_not_called()


def test_l05_shutdown_restores_and_stale_receiver_is_inert(running):
    r = running
    callback = r.runtime.transport.subscriptions[r.runtime.topics[r.identity]["set"]][0]
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes = len(hardware.writes)
    r.runtime.stop()
    callback("irrelevant", b"ON", retained=False)
    assert len(hardware.writes) == writes
    assert not r.manager.receivers and "on_api_get" not in vars(r.usb)


def test_l06_disable_event_immediately_gates_and_unsubscribes(running):
    r = running
    previous_transport = r.runtime.transport
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert not r.runtime.ready
    assert r.runtime.worker.wait_idle()
    assert r.runtime.transport is None and not previous_transport.subscriptions
    assert "pending restart" in r.runtime.last_error


def test_l01_unknown_connection_bootstraps_only_from_retained(running):
    r = running
    r.runtime.connection_observed = False
    r.runtime.connected = None
    r.runtime._bootstrap("test/mqtt", b"connected", retained=False)
    assert r.runtime.connected is None
    r.runtime._bootstrap("test/mqtt", b"connected", retained=True)
    assert r.runtime.worker.wait_idle()
    assert r.runtime.connected is True


def test_l07_invalid_plugin_messages_and_irrelevant_events_are_ignored(running):
    r = running
    epoch = r.runtime.worker.current_epoch()
    for sender, payload in [
        ("other", {"connected": False}),
        ("mqtt", []),
        ("mqtt", {"connected": 1}),
    ]:
        r.runtime.on_plugin_message(sender, payload)
    r.runtime.on_event("OtherEvent", {"id": "unrelated"})
    assert r.runtime.worker.current_epoch() == epoch


def test_l03_overlapping_birth_and_lwt_is_rejected(running):
    r = running
    r.runtime.settings.set(["ha_birth_topic"], "test/mqtt")
    r.runtime.settings_updated()
    assert r.runtime.worker.wait_idle()
    assert not r.runtime.ready and "must differ" in r.runtime.last_error


def test_d05_failed_identity_save_restores_old_identity(running):
    r = running
    r.runtime.on_plugin_message("mqtt", {"connected": False})
    assert r.runtime.worker.wait_idle()
    old = r.runtime.settings.get(["instance_uuid"])
    r.runtime.settings.save = Mock(side_effect=OSError())
    with pytest.raises(OSError):
        r.runtime.clone_identity(True)
    assert r.runtime.settings.get(["instance_uuid"]) == old


def test_f14_publish_exception_does_not_change_local_result(running):
    r = running
    r.mqtt._mqtt.publish.side_effect = OSError("transport")
    relay = r.runtime.registry.entries[r.identity].relay
    assert relay.state(1, True) is None
    assert r.runtime.worker.wait_idle()
    assert r.runtime.worker.snapshots[r.identity]["actual"] is True
    assert r.runtime.transport.failed > 0


@pytest.mark.parametrize("dependency", ["usbrelaycontrol", "mqtt"])
@pytest.mark.parametrize("operation", ["disable", "uninstall"])
def test_review_dependency_loss_publishes_offline_before_unsubscribe(
    running, dependency, operation
):
    r = running
    availability = r.runtime.topics[r.identity]["availability"]
    transport = r.runtime.transport
    calls = []
    publish = transport.helpers["mqtt_publish"]
    unsubscribe = transport.helpers["mqtt_unsubscribe"]

    def observed_publish(topic, payload, **kwargs):
        calls.append(("publish", topic, payload, kwargs))
        return publish(topic, payload, **kwargs)

    def observed_unsubscribe(*args, **kwargs):
        calls.append(("unsubscribe", kwargs["topic"]))
        return unsubscribe(*args, **kwargs)

    transport.helpers["mqtt_publish"] = observed_publish
    transport.helpers["mqtt_unsubscribe"] = observed_unsubscribe
    hardware = r.runtime.registry.entries[r.identity].relay.h
    writes = len(hardware.writes)
    r.runtime.on_event(f"plugin_pluginmanager_{operation}_plugin", {"id": dependency})
    assert r.runtime.worker.wait_idle()
    assert not r.runtime.ready and r.runtime.transport is None
    assert not transport.subscriptions and len(hardware.writes) == writes
    offline = next(
        (i for i, call in enumerate(calls) if call[:3] == ("publish", availability, "offline")),
        None,
    )
    assert offline is not None, "Dependency loss must retire the previous online availability"
    assert calls[offline][3] == {"retained": True, "qos": 0, "allow_queueing": False}
    assert offline < next(i for i, call in enumerate(calls) if call[0] == "unsubscribe")


def test_review_offline_dependency_loss_republishes_unavailable_after_reconnect(running):
    r = running
    availability = r.runtime.topics[r.identity]["availability"]
    r.runtime.on_plugin_message("mqtt", {"connected": False})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.reset_mock()
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.assert_not_called()
    replacement = mqtt()
    r.manager.infos["mqtt"].implementation = replacement
    r.runtime.on_plugin_message("mqtt", {"connected": True})
    assert r.runtime.worker.wait_idle()
    replacement._mqtt.publish.assert_any_call(availability, payload="offline", qos=0, retain=True)
    r.mqtt._mqtt.publish.assert_not_called()
    assert not r.runtime.ready and r.runtime.adapter is None


@pytest.mark.parametrize("connection", [False, None])
def test_review_dependency_loss_never_publishes_while_connection_is_unknown_or_offline(
    running, connection
):
    r = running
    r.runtime.connected = connection
    r.mqtt._mqtt.publish.reset_mock()
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.assert_not_called()
    assert not r.runtime.ready and r.runtime.transport is None


def test_review_offline_publication_failure_still_unbinds(running):
    r = running
    previous = r.runtime.transport
    r.mqtt._mqtt.publish.side_effect = OSError("synthetic transport failure")
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    assert previous.failed > 0 and not previous.subscriptions
    assert r.runtime.transport is None and r.runtime.adapter is None


def test_review_dependency_loss_never_publishes_old_identity(running):
    r = running
    r.runtime.settings.set(["instance_uuid"], str(uuid4()))
    r.mqtt._mqtt.publish.reset_mock()
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.assert_not_called()


@pytest.mark.parametrize("failure", ["missing_plugin", "version", "helpers", "lookup"])
def test_review_reconnect_offline_publish_requires_compatible_current_mqtt(running, failure):
    r = running
    r.runtime.on_event("plugin_pluginmanager_disable_plugin", {"id": "usbrelaycontrol"})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.reset_mock()
    if failure == "missing_plugin":
        r.manager.infos.pop("mqtt")
    elif failure == "version":
        r.manager.infos["mqtt"].version = "unsupported"
    elif failure == "helpers":
        r.manager.get_helpers = Mock(return_value={})
    else:
        r.manager.get_helpers = Mock(side_effect=RuntimeError("synthetic lookup failure"))
    r.runtime.on_plugin_message("mqtt", {"connected": True})
    assert r.runtime.worker.wait_idle()
    r.mqtt._mqtt.publish.assert_not_called()
    assert not r.runtime.ready and r.runtime.adapter is None
