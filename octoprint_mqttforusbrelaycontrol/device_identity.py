"""Persist only the last confirmed optional discovery identity in companion data."""

import json
import os
import tempfile
from pathlib import Path

from .discovery import valid_device_identifier


class DeviceIdentityCache:
    def __init__(self, directory):
        self.path = Path(directory) / "device-identity.json"
        self.value = None
        self.persisted = None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            value = data["device"]
            if (
                data["schema"] == 1
                and valid_device_identifier(value["node_id"])
                and (value.get("node_name") is None or valid_device_identifier(value["node_name"]))
            ):
                self.value = {"node_id": value["node_id"], "node_name": value.get("node_name")}
                self.persisted = dict(self.value)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def remember(self, value):
        self.value = dict(value)
        if value == self.persisted and self.path.is_file():
            return True
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".device-identity-", dir=self.path.parent
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"schema": 1, "device": self.value}, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self.persisted = dict(value)
            return True
        except OSError:
            return False
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
