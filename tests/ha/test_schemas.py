"""Validate actual discovery with the separately installed Home Assistant schemas."""

from uuid import uuid4

import pytest

pytest.importorskip(
    "homeassistant", reason="Use the documented isolated Home Assistant schema environment"
)
import voluptuous as vol
from homeassistant.components.mqtt.fan import DISCOVERY_SCHEMA as FAN_SCHEMA
from homeassistant.components.mqtt.light.schema_basic import DISCOVERY_SCHEMA_BASIC as LIGHT_SCHEMA
from homeassistant.components.mqtt.switch import DISCOVERY_SCHEMA as SWITCH_SCHEMA

from octoprint_mqttforusbrelaycontrol.discovery import discovery_configuration
from octoprint_mqttforusbrelaycontrol.mqtt_integration import relay_topics
from octoprint_mqttforusbrelaycontrol.relay_registry import RelayEntry, relay_id


@pytest.mark.parametrize(
    "domain,schema", [("switch", SWITCH_SCHEMA), ("light", LIGHT_SCHEMA), ("fan", FAN_SCHEMA)]
)
@pytest.mark.parametrize(
    "device",
    [None, {"identifiers": ["ABC123"], "name": "OctoPrint"}, {"identifiers": ["Custom-device-ID"]}],
)
def test_i03_actual_home_assistant_discovery_schema(domain, schema, device):
    identity = str(uuid4())
    entry = RelayEntry(
        relay_id(identity, "16c0", "05df", 1),
        "16c0",
        "05df",
        1,
        0,
        "16c0:05df",
        "Work light",
        "active_high",
        None,
        1,
        True,
        domain,
    )
    topics = relay_topics("test", identity, entry)
    _, payload = discovery_configuration(
        entry, identity, "homeassistant", topics, "test/mqtt", "", device=device
    )
    validated = schema(payload)
    assert validated["retain"] is False
    assert validated["optimistic"] is False
    assert validated["availability_mode"] == "all"
    invalid = dict(payload, command_topic="test/#")
    with pytest.raises(vol.Invalid):
        schema(invalid)
