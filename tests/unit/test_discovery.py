"""Identity, discovery and durable ownership regressions."""

import json
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from octoprint_mqttforusbrelaycontrol.discovery import DiscoveryLedger, discovery_configuration
from octoprint_mqttforusbrelaycontrol.mqtt_integration import relay_topics
from octoprint_mqttforusbrelaycontrol.relay_registry import RelayRegistry, normalize_usb_id
from tests.upstream import original


@pytest.fixture
def configured():
    plugin = original()
    plugin.on_after_startup()
    registry = RelayRegistry(str(uuid4()))
    registry.rebuild(plugin)
    return plugin, registry, next(iter(registry.entries.values()))


@pytest.mark.parametrize("domain", ["switch", "light", "fan"])
def test_d01_f21_binary_discovery(configured, domain):
    _, registry, entry = configured
    entry = replace(entry, entity_type=domain)
    topics = relay_topics("test", registry.instance_uuid, entry)
    topic, payload = discovery_configuration(
        entry, registry.instance_uuid, "homeassistant", topics, "test/mqtt", ""
    )
    assert f"/{domain}/" in topic
    assert payload["retain"] is False and payload["optimistic"] is False
    assert payload["availability_mode"] == "all"
    assert len(payload["availability"]) == 2
    assert not any(key.startswith(("brightness", "percentage", "color")) for key in payload)
    assert "schema" not in payload


def test_d02_d03_d04_retirements_survive_handoff_and_reactivation(configured, tmp_path):
    _, registry, entry = configured
    topics = relay_topics("test", registry.instance_uuid, entry)
    topic, payload = discovery_configuration(
        entry, registry.instance_uuid, "homeassistant", topics, "test/mqtt", ""
    )
    ledger = DiscoveryLedger(tmp_path, registry.instance_uuid)
    ledger.update({topic: payload}, {topics["availability"]})
    ledger.update({}, set())
    transport = Mock()
    ledger.submit_retirements(transport)
    transport.publish.assert_any_call(topic, "")
    restored = DiscoveryLedger(tmp_path, registry.instance_uuid)
    assert topic in restored.tombstones
    restored.update({topic: payload}, {topics["availability"]})
    assert not restored.tombstones and not restored.retired_availability


def test_corrupt_ledger_refuses_foreign_topic(configured, tmp_path):
    _, registry, _ = configured
    ledger = DiscoveryLedger(tmp_path, registry.instance_uuid)
    ledger.update({}, set())
    data = json.loads(ledger.path.read_text())
    data["tombstones"] = ["homeassistant/switch/foreign/config"]
    ledger.path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="outside this instance"):
        DiscoveryLedger(tmp_path, registry.instance_uuid)
    assert json.loads(ledger.path.read_text()) == data


def test_d03_atomic_write_failure_preserves_last_durable_ownership(
    configured, tmp_path, monkeypatch
):
    import octoprint_mqttforusbrelaycontrol.discovery as module

    _, registry, entry = configured
    topic, payload = discovery_configuration(
        entry,
        registry.instance_uuid,
        "homeassistant",
        relay_topics("test", registry.instance_uuid, entry),
        "test/mqtt",
        "",
    )
    ledger = DiscoveryLedger(tmp_path, registry.instance_uuid)
    ledger.update({topic: payload}, set())
    before = ledger.path.read_bytes()
    monkeypatch.setattr(
        module.os, "replace", Mock(side_effect=OSError("Synthetic storage failure"))
    )
    with pytest.raises(OSError):
        ledger.update({}, set())
    assert ledger.path.read_bytes() == before and topic in ledger.current
    assert not list(tmp_path.glob(".discovery-*"))


def test_f18_f19_f20_identity_ignores_name_order_and_hex_spelling(configured):
    plugin, registry, entry = configured
    configurations = plugin._settings.get(["usbrelay_configurations"])
    configurations[0]["name"] = "Renamed"
    configurations[0]["vendor"] = "16C0"
    plugin._settings.set(["usbrelay_configurations"], configurations)
    plugin.relays["16C0:05df"] = entry.relay
    registry.rebuild(plugin)
    assert next(iter(registry.entries)) == entry.id
    other = RelayRegistry(str(uuid4()))
    other.rebuild(plugin)
    assert next(iter(other.entries)) != entry.id


def test_d06_duplicates_and_invalid_channel_fail_closed(configured):
    plugin, registry, _ = configured
    configurations = plugin._settings.get(["usbrelay_configurations"])
    plugin._settings.set(["usbrelay_configurations"], configurations * 2)
    registry.rebuild(plugin)
    assert not registry.entries and registry.errors
    configurations[0]["relaynumber"] = 0
    plugin._settings.set(["usbrelay_configurations"], configurations)
    registry.rebuild(plugin)
    assert not registry.entries


@pytest.mark.parametrize("value", ["10000", "-1", "GGGG", " 16c0", 5824, "+16c0", "16_c0"])
def test_invalid_usb_id(value):
    with pytest.raises(ValueError):
        normalize_usb_id(value)
