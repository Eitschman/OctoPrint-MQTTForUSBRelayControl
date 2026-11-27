"""Actual isolated Home Assistant MQTT discovery runtime, without physical devices."""

import asyncio
import copy
import json
import os
from types import MappingProxyType
from uuid import uuid4

import pytest
import yaml

pytest.importorskip("homeassistant")
import paho.mqtt.client as mqtt
from homeassistant import loader
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from octoprint_mqttforusbrelaycontrol.discovery import discovery_configuration
from octoprint_mqttforusbrelaycontrol.mqtt_integration import relay_topics
from octoprint_mqttforusbrelaycontrol.relay_registry import RelayEntry, relay_id
from tests.services import broker, free_port

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_HA_TESTS") != "1", reason="Set RUN_HA_TESTS=1 for disposable HA runtime"
)


def test_i03_actual_home_assistant_entities(tmp_path):
    with broker(tmp_path / "broker") as port:
        asyncio.run(asyncio.wait_for(run_runtime(tmp_path / "ha", port), timeout=60))


async def run_runtime(directory, port):
    directory.mkdir()
    hass = HomeAssistant(str(directory))
    loader.async_setup(hass)
    configuration = {
        "homeassistant": {"name": "Disposable MQTT test", "time_zone": "UTC", "country": "DE"},
        "http": {"server_host": "127.0.0.1", "server_port": free_port()},
    }
    (directory / "configuration.yaml").write_text(yaml.safe_dump(configuration), encoding="utf-8")
    assert await async_from_config_dict(configuration, hass) is hass
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        assert await async_setup_component(hass, "mqtt", configuration)
        entry = ConfigEntry(
            domain="mqtt",
            version=2,
            minor_version=1,
            data={"broker": "127.0.0.1", "port": port, "protocol": "5"},
            options={"discovery": True},
            source="user",
            title="Disposable test broker",
            unique_id=None,
            subentries_data=[],
            discovery_keys=MappingProxyType({}),
        )
        await hass.config_entries.async_add(entry)
        await hass.async_start()
        await hass.async_block_till_done()
        await asyncio.to_thread(client.connect, "127.0.0.1", port)
        client.loop_start()
        instance_uuid = str(uuid4())
        configurations = {}
        for channel, domain in enumerate(("switch", "light", "fan"), 1):
            relay = RelayEntry(
                relay_id(instance_uuid, "16c0", "05df", channel),
                "16c0",
                "05df",
                channel,
                channel - 1,
                "16c0:05df",
                f"Synthetic {domain}",
                "active_high",
                None,
                1,
                True,
                domain,
            )
            topics = relay_topics("isolated", instance_uuid, relay)
            topic, payload = discovery_configuration(
                relay, instance_uuid, "homeassistant", topics, "isolated/mqtt", "Test relays"
            )
            configurations[domain] = (topic, payload)
            await asyncio.to_thread(
                client.publish(topic, json.dumps(payload), 1, True).wait_for_publish, 5
            )
            await asyncio.to_thread(
                client.publish("isolated/mqtt", "connected", 1, True).wait_for_publish, 5
            )
            await asyncio.to_thread(
                client.publish(topics["availability"], "online", 1, True).wait_for_publish, 5
            )
            await asyncio.to_thread(
                client.publish(topics["state"], "ON", 1, True).wait_for_publish, 5
            )

        async def until(predicate):
            deadline = asyncio.get_running_loop().time() + 10
            while asyncio.get_running_loop().time() < deadline:
                if predicate():
                    return
                await asyncio.sleep(0.1)
            raise AssertionError("Home Assistant did not reach the expected current state")

        def entities():
            return [
                state
                for state in hass.states.async_all()
                if state.domain in ("switch", "light", "fan")
            ]

        async def publish(topic, payload):
            await asyncio.to_thread(client.publish(topic, payload, 1, True).wait_for_publish, 5)

        await until(
            lambda: len(entities()) == 3 and all(state.state == "on" for state in entities())
        )
        from homeassistant.helpers import device_registry

        devices = device_registry.async_get(hass).devices
        assert (
            sum(
                any(
                    value.endswith(instance_uuid.replace("-", ""))
                    for _, value in device.identifiers
                )
                for device in devices
            )
            == 1
        )
        # A discovery update must move the existing entity, not create a duplicate
        # or merge the old device's identifier into the shared printer device.
        from homeassistant.helpers import entity_registry

        registry = entity_registry.async_get(hass)
        switch_id = relay_id(instance_uuid, "16c0", "05df", 1)
        entity_id = registry.async_get_entity_id("switch", "mqtt", switch_id)
        assert entity_id is not None
        old_device_id = registry.async_get(entity_id).device_id
        await publish(
            "homeassistant/binary_sensor/synthetic_printer/config",
            json.dumps(
                {
                    "name": "Connected",
                    "unique_id": "synthetic_printer_connected",
                    "state_topic": "isolated/printer/state",
                    "device": {
                        "identifiers": ["ABC123"],
                        "name": "OctoPrint",
                        "model": "Synthetic printer",
                    },
                }
            ),
        )
        await until(
            lambda: registry.async_get_entity_id(
                "binary_sensor", "mqtt", "synthetic_printer_connected"
            )
            is not None
        )
        printer_entity = registry.async_get_entity_id(
            "binary_sensor", "mqtt", "synthetic_printer_connected"
        )
        printer_device_id = registry.async_get(printer_entity).device_id
        assert printer_device_id != old_device_id
        switch_topic, switch_payload = configurations["switch"]
        shared = copy.deepcopy(switch_payload)
        shared["device"] = {"identifiers": ["ABC123"], "name": "OctoPrint"}
        await publish(switch_topic, json.dumps(shared))
        await until(lambda: registry.async_get(entity_id).device_id == printer_device_id)
        assert len(entities()) == 3
        assert registry.async_get_entity_id("switch", "mqtt", switch_id) == entity_id
        assert (
            device_registry.async_get(hass).devices[printer_device_id].model == "Synthetic printer"
        )
        assert device_registry.async_get(hass).devices[printer_device_id].identifiers == {
            ("mqtt", "ABC123")
        }
        await publish(switch_topic, json.dumps(switch_payload))
        await until(lambda: registry.async_get(entity_id).device_id == old_device_id)
        assert registry.async_get(printer_entity).device_id == printer_device_id
        await publish("isolated/mqtt", "disconnected")
        await until(lambda: all(state.state == "unavailable" for state in entities()))
        await publish("isolated/mqtt", "connected")
        await until(lambda: all(state.state == "on" for state in entities()))
        switch_id = relay_id(instance_uuid, "16c0", "05df", 1)
        await publish(f"homeassistant/switch/{switch_id}/config", "")
        await until(lambda: len(entities()) == 2)
        changed = RelayEntry(
            switch_id,
            "16c0",
            "05df",
            1,
            0,
            "16c0:05df",
            "Changed light",
            "active_high",
            None,
            1,
            True,
            "light",
        )
        changed_topics = relay_topics("isolated", instance_uuid, changed)
        changed_topic, changed_payload = discovery_configuration(
            changed, instance_uuid, "homeassistant", changed_topics, "isolated/mqtt", "Test relays"
        )
        await publish(changed_topic, json.dumps(changed_payload))
        await until(
            lambda: len(entities()) == 3
            and sum(state.domain == "light" for state in entities()) == 2
            and all(state.state == "on" for state in entities())
        )
    finally:
        client.disconnect()
        client.loop_stop()
        await hass.async_stop()
