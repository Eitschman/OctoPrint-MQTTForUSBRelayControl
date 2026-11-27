"""Read-only projection of the original configuration and existing objects."""

import re
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID


def normalize_usb_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0x)?[0-9a-f]+", value, re.IGNORECASE):
        raise ValueError("USB identifiers must be hexadecimal strings")
    number = int(value, 16)
    if not 0 <= number <= 0xFFFF:
        raise ValueError("USB identifier is outside the 16-bit range")
    return f"{number:04x}"


def relay_id(instance_uuid, vendor, product, channel):
    return f"{UUID(instance_uuid).hex}_{vendor}_{product}_{channel}"


@dataclass(frozen=True)
class RelayEntry:
    id: str
    vendor: str
    product: str
    channel: int
    index: int
    original_key: str
    original_name: str
    active_mode: str
    relay: Any
    generation: int
    enabled: bool = False
    entity_type: str = "switch"
    display_name: str = ""

    def logical(self, physical: bool) -> bool:
        return physical if self.active_mode == "active_high" else not physical

    def physical(self, logical: bool) -> bool:
        return logical if self.active_mode == "active_high" else not logical


class RelayRegistry:
    def __init__(self, instance_uuid):
        self.instance_uuid = str(UUID(instance_uuid))
        self.generation = 0
        self.entries: dict[str, RelayEntry] = {}
        self.errors: list[str] = []

    def rebuild(self, original, options=None):
        self.generation += 1
        options = options or {}
        configurations = original._settings.get(["usbrelay_configurations"])
        if not isinstance(configurations, list) or not isinstance(original.relays, dict):
            raise ValueError("Unsupported original relay configuration")
        entries = {}
        duplicates = set()
        errors = []
        for index, config in enumerate(configurations):
            try:
                vendor = normalize_usb_id(config["vendor"])
                product = normalize_usb_id(config["product"])
                raw_channel = config["relaynumber"]
                if isinstance(raw_channel, bool) or str(raw_channel) not in tuple(
                    map(str, range(1, 9))
                ):
                    raise ValueError("Relay channel must be between 1 and 8")
                channel = int(raw_channel)
                mode = config["active_mode"]
                if mode not in ("active_high", "active_low"):
                    raise ValueError("Unsupported relay active mode")
                key = f"{config['vendor']}:{config['product']}"
                existing = original.relays.get(key)
                if existing is None or not callable(getattr(existing, "state", None)):
                    raise ValueError("Original relay object is unavailable")
                identity = relay_id(self.instance_uuid, vendor, product, channel)
                settings = options.get(identity, {})
                domain = settings.get("entity_type", "switch")
                if domain not in ("switch", "light", "fan"):
                    raise ValueError("Unsupported entity type")
                entry = RelayEntry(
                    identity,
                    vendor,
                    product,
                    channel,
                    index,
                    key,
                    str(config.get("name", "")),
                    mode,
                    existing,
                    self.generation,
                    settings.get("enabled") is True,
                    domain,
                    str(settings.get("display_name", "")),
                )
                if identity in entries:
                    duplicates.add(identity)
                entries[identity] = entry
            except (KeyError, TypeError, ValueError) as error:
                errors.append(f"Configuration {index}: {error}")
        for identity in duplicates:
            del entries[identity]
            errors.append(f"Duplicate relay channel: {identity}")
        self.entries, self.errors = entries, errors
        return self.entries

    def for_object(self, relay, channel=None):
        return [
            entry
            for entry in self.entries.values()
            if entry.relay is relay and (channel in (None, 0) or entry.channel == channel)
        ]

    def current(self, identity: str, generation: int) -> Optional[RelayEntry]:
        entry = self.entries.get(identity)
        return entry if entry and entry.generation == generation else None
