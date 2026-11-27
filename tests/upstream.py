"""Load pinned, checksum-verified upstream code without opening hardware."""

import ast
import copy
import hashlib
import json
import logging
from collections import defaultdict, deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import flask
import octoprint.plugin as octoprint_plugin

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    manifest = json.loads((ROOT / "tests/fixtures/upstream-manifest.json").read_text())
    entry = next(item for item in manifest["files"] if item["path"] == relative)
    path = ROOT / "artifacts/upstream" / relative
    if not path.is_file():
        raise RuntimeError("Run python tools/prepare_upstream.py before upstream tests")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise RuntimeError(f"Invalid upstream fixture: {relative}")
    return data.decode("utf-8")


def extract(relative, name, namespace, methods=None):
    tree = ast.parse(source(relative))
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    if methods is not None:
        node.bases = []
        node.body = [
            item for item in node.body if isinstance(item, ast.FunctionDef) and item.name in methods
        ]
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, relative, "exec"), namespace)
    return namespace[name]


class Settings:
    def __init__(self, data=None):
        self.data = copy.deepcopy(data or {})

    def get(self, path):
        result = self.data
        for key in path:
            result = result.get(key) if isinstance(result, dict) else None
        return copy.deepcopy(result)

    def get_boolean(self, path):
        return bool(self.get(path))

    def get_all_data(self):
        return self.get([])

    def set(self, path, value):
        if not path:
            self.data = copy.deepcopy(value)
            return
        target = self.data
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = copy.deepcopy(value)

    def save(self, **kwargs):
        return None

    def clean_all_data(self):
        self.data = {}


class Hardware:
    def __init__(self):
        self.bits = 0
        self.writes = []
        self.reads = 0
        self.closed = False
        self.write_result = 2
        self.write_error = None
        self.read_error = None
        self.empty_report = False

    def open(self, *args):
        pass

    def set_nonblocking(self, *args):
        pass

    def close(self):
        self.closed = True

    def send_feature_report(self, message):
        self.writes.append(message)
        if self.write_error:
            raise self.write_error
        if self.write_result >= 0:
            if message[0] in (0xFE, 0xFC):
                self.bits = 255 if message[0] == 0xFE else 0
            elif message[0] == 0xFF:
                self.bits |= 1 << (message[1] - 1)
            else:
                self.bits &= ~(1 << (message[1] - 1))
        return self.write_result

    def get_feature_report(self, *args):
        self.reads += 1
        if self.read_error:
            raise self.read_error
        return [] if self.empty_report else [0] * 7 + [self.bits]


def relay_class():
    return extract(
        "usbrelay/octoprint_usbrelaycontrol/relay.py",
        "Relay",
        {
            "__name__": "octoprint_usbrelaycontrol.relay",
            "hid": SimpleNamespace(device=Hardware),
            "atexit": Mock(),
        },
    )


def original(configurations=None):
    namespace = {
        "__name__": "octoprint_usbrelaycontrol",
        "octoprint": SimpleNamespace(plugin=octoprint_plugin),
        "Relay": relay_class(),
        "flask": flask,
        "Permissions": SimpleNamespace(
            PLUGIN_USBRELAYCONTROL_CONTROL=SimpleNamespace(can=lambda: True)
        ),
    }
    cls = extract(
        "usbrelay/octoprint_usbrelaycontrol/__init__.py", "USBRelayControlPlugin", namespace
    )
    instance = cls()
    instance.relays = {}
    instance._logger = logging.getLogger("test.original")
    instance._settings = Settings(
        {
            "usbrelay_configurations": configurations
            or [
                {
                    "vendor": "16c0",
                    "product": "05df",
                    "relaynumber": "1",
                    "active_mode": "active_high",
                    "default_state": "default_off",
                    "name": "Work light",
                }
            ]
        }
    )
    return instance


MQTT_METHODS = {
    "mqtt_publish",
    "mqtt_subscribe",
    "mqtt_unsubscribe",
    "_on_mqtt_connect",
    "_on_mqtt_disconnect",
    "_on_mqtt_message",
    "_get_topic",
}


def mqtt(version="0.8.20"):
    cls = extract(
        f"mqtt-{version}/octoprint_mqtt/__init__.py",
        "MqttPlugin",
        {"json": json, "six": SimpleNamespace(string_types=(str,))},
        MQTT_METHODS,
    )
    instance = cls()
    instance._logger = logging.getLogger("test.mqtt")
    instance._settings = Settings(
        {
            "broker": {"retain": True, "lwRetain": True},
            "publish": {"baseTopic": "test/", "lwTopic": "mqtt", "lwActive": True},
        }
    )
    instance._mqtt = Mock()
    instance._mqtt_connected = True
    instance._mqtt_subscriptions = []
    instance._mqtt_publish_queue = deque()
    instance._mqtt_subscribe_queue = []
    instance._mqtt_reset_state = False
    instance._plugin_manager = Mock()
    instance._identifier = "mqtt"
    instance.LWT_CONNECTED = "connected"
    return instance


def lifecycle_class():
    return extract(
        "octoprint-2.0.1/src/octoprint/server/__init__.py",
        "LifecycleManager",
        {"defaultdict": defaultdict, "logging": logging},
    )
