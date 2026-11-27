"""Conservative checks for the deliberately narrow upstream adapter."""

import inspect
from dataclasses import dataclass
from typing import Any

from octoprint.util import time_this

from .constants import SUPPORTED_MQTT_VERSIONS, SUPPORTED_USB_VERSIONS

_TIMING_WRAPPER_CODE = time_this()(lambda: None).__code__


def original_method(method):
    for _ in range(16):
        if not hasattr(method, "__wrapped__"):
            return method
        if getattr(method, "__code__", None) is not _TIMING_WRAPPER_CODE:
            raise ValueError("Unknown original method wrapper")
        method = method.__wrapped__
    raise ValueError("Excessive original wrapper depth")


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    errors: tuple[str, ...]


def check_mqtt_compatibility(mqtt_version, helpers):
    errors = []
    if mqtt_version not in SUPPORTED_MQTT_VERSIONS:
        errors.append("Unsupported MQTT version")
    for helper_name, helper_args, helper_kwargs in (
        (
            "mqtt_publish",
            ("topic", "payload"),
            {"retained": True, "qos": 0, "allow_queueing": False},
        ),
        ("mqtt_subscribe", ("topic", lambda *a, **k: None), {}),
        ("mqtt_unsubscribe", (lambda *a, **k: None,), {"topic": "topic"}),
    ):
        try:
            inspect.signature(helpers[helper_name]).bind(*helper_args, **helper_kwargs)
        except (KeyError, TypeError, ValueError):
            errors.append(f"Unsupported MQTT helper: {helper_name}")
    return CompatibilityResult(not errors, tuple(errors))


def check_compatibility(original, usb_version, mqtt_version, helpers):
    errors = list(check_mqtt_compatibility(mqtt_version, helpers).errors)
    if usb_version not in SUPPORTED_USB_VERSIONS:
        errors.append("Unsupported USB Relay Control version")
    expected: dict[str, tuple[Any, ...]] = {
        "on_after_startup": (),
        "on_settings_save": ({},),
        "on_api_command": ("get", {}),
        "on_api_get": (None,),
    }
    for name, args in expected.items():
        method = getattr(original, name, None)
        try:
            if not callable(method):
                raise ValueError()
            method = original_method(method)
            inspect.signature(method).bind(*args)
            module = getattr(method, "__module__", "")
            if not module.startswith("octoprint_usbrelaycontrol"):
                raise ValueError()
        except (TypeError, ValueError):
            errors.append(f"Unsupported original method: {name}")
    if not isinstance(getattr(original, "relays", None), dict):
        errors.append("Unsupported original relay collection")
    relays = getattr(original, "relays", {})
    for relay in relays.values() if isinstance(relays, dict) else ():
        try:
            method = relay.state
            if hasattr(method, "__wrapped__"):
                raise ValueError()
            inspect.signature(method).bind(1, on=None)
            if not method.__module__.startswith("octoprint_usbrelaycontrol"):
                raise ValueError()
        except (AttributeError, TypeError, ValueError):
            errors.append("Unsupported relay state method")
    return CompatibilityResult(not errors, tuple(errors))
