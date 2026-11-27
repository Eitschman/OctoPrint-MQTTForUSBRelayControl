"""Minimal binary Home Assistant discovery and durable owned deletion intent."""

import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

from .mqtt_integration import concrete_topic, topic_prefix


def valid_device_identifier(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 128
        and value == value.strip()
        and value.isprintable()
    )


def discovery_device(config, mqtt_prefix, existing=None):
    """Resolve device grouping independently of relay identity and topic ownership."""
    name = config["device_name"]
    override = config["device_identifier"]
    if override:
        if not valid_device_identifier(override):
            raise ValueError("Device identifier must be printable text of at most 128 characters")
        identifier, source = override, "custom"
    elif config["use_octoprint_device"] and existing:
        identifier, source = existing["node_id"], "octoprint"
        name = name or existing.get("node_name")
    else:
        identifier = f"mqttforusbrelaycontrol_{UUID(config['instance_uuid']).hex}"
        source = "separate"
        name = name or mqtt_prefix
    device = {"identifiers": [identifier]}
    if name:
        device["name"] = name
    return device, source


def discovery_configuration(
    entry, instance_uuid, prefix, topics, lwt_topic, device_name, device=None
):
    if entry.entity_type not in ("switch", "light", "fan"):
        raise ValueError("Unsupported Home Assistant entity type")
    topic = concrete_topic(f"{topic_prefix(prefix)}/{entry.entity_type}/{entry.id}/config")
    payload = {
        "name": entry.display_name or entry.original_name or f"Relay {entry.channel}",
        "unique_id": entry.id,
        "command_topic": topics["set"],
        "state_topic": topics["state"],
        "payload_on": "ON",
        "payload_off": "OFF",
        "optimistic": False,
        "retain": False,
        "qos": 0,
        "availability_mode": "all",
        "availability": [
            {
                "topic": lwt_topic,
                "payload_available": "connected",
                "payload_not_available": "disconnected",
            },
            {
                "topic": topics["availability"],
                "payload_available": "online",
                "payload_not_available": "offline",
            },
        ],
        "device": copy.deepcopy(device)
        if device is not None
        else {
            "identifiers": [f"mqttforusbrelaycontrol_{UUID(instance_uuid).hex}"],
            "name": device_name or "OctoPrint USB relays",
        },
    }
    for value in (topics["set"], topics["state"], topics["availability"], lwt_topic):
        concrete_topic(value)
    return topic, payload


class DiscoveryLedger:
    """A helper return is not an ACK; tombstones survive successful submission."""

    def __init__(self, directory, instance_uuid):
        self.instance_uuid = str(UUID(instance_uuid))
        self.path = Path(directory) / f"discovery-{self.instance_uuid}.json"
        self.current = {}
        self.tombstones = set()
        self.availability = set()
        self.retired_availability = set()
        self._discovery_pattern = re.compile(
            rf".+/(switch|light|fan)/{UUID(instance_uuid).hex}_[0-9a-f]{{4}}_[0-9a-f]{{4}}_[1-8]/config"
        )
        self._availability_pattern = re.compile(
            rf".+/usbrelay/{re.escape(self.instance_uuid)}/[0-9a-f]{{4}}-[0-9a-f]{{4}}/[1-8]/availability"
        )
        if self.path.exists():
            self._load()

    def _owned(self, topic, availability=False):
        concrete_topic(topic)
        pattern = self._availability_pattern if availability else self._discovery_pattern
        if not pattern.fullmatch(topic):
            raise ValueError("Discovery ledger contains a topic outside this instance")
        return topic

    def _load(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema") != 1 or data.get("instance_uuid") != self.instance_uuid:
            raise ValueError("Unsupported discovery ledger identity or schema")
        current = data["current"]
        if not isinstance(current, dict) or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in current.values()
        ):
            raise ValueError("Invalid discovery ledger hashes")
        for topic in current:
            self._owned(topic)
        tombstones = {self._owned(topic) for topic in data["tombstones"]}
        availability = {self._owned(topic, True) for topic in data["availability"]}
        retired = {self._owned(topic, True) for topic in data["retired_availability"]}
        self.current, self.tombstones = current, tombstones - set(current)
        self.availability, self.retired_availability = availability, retired - availability

    def update(self, configurations, availability):
        current = {
            self._owned(topic): hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest()
            for topic, payload in configurations.items()
        }
        availability = {self._owned(topic, True) for topic in availability}
        tombstones = (self.tombstones | (set(self.current) - set(current))) - set(current)
        retired = (self.retired_availability | (self.availability - availability)) - availability
        data = {
            "schema": 1,
            "instance_uuid": self.instance_uuid,
            "current": current,
            "tombstones": sorted(tombstones),
            "availability": sorted(availability),
            "retired_availability": sorted(retired),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".discovery-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.current, self.tombstones = current, tombstones
        self.availability, self.retired_availability = availability, retired

    def submit_retirements(self, transport, permit=lambda: True):
        for topic in sorted(self.retired_availability - self.availability):
            if not permit():
                return
            transport.publish(topic, "offline")
        for topic in sorted(self.tombstones - set(self.current)):
            if not permit():
                return
            transport.publish(topic, "")
