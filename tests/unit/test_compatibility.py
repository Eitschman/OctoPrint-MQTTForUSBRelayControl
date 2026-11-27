"""Reject changed contracts while accepting OctoPrint's own timing wrappers."""

import functools

import pytest
from octoprint.util import time_this

from octoprint_mqttforusbrelaycontrol.compatibility import check_compatibility
from tests.upstream import mqtt, original


def check(usb, usb_version="1.0.0", mqtt_version="0.8.20", helpers=None):
    transport = mqtt()
    if helpers is None:
        helpers = {
            name: getattr(transport, name)
            for name in ("mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
        }
    return check_compatibility(usb, usb_version, mqtt_version, helpers)


def test_a01_supported_and_octoprint_timing_wrappers():
    usb = original()
    usb.on_after_startup()
    for name in ("on_after_startup", "on_settings_save", "on_api_command", "on_api_get"):
        setattr(usb, name, time_this()(getattr(usb, name)))
    assert check(usb).compatible


@pytest.mark.parametrize(
    "change", ["version", "mqtt", "signature", "collection", "wrapper", "relay", "helper"]
)
def test_a01_unknown_contract_fails_without_mutation(change):
    usb = original()
    usb.on_after_startup()
    arguments = {}
    if change == "version":
        arguments["usb_version"] = "2.0.0"
    if change == "mqtt":
        arguments["mqtt_version"] = "0.8.18"
    if change == "signature":
        usb.on_api_get = lambda: None
    if change == "collection":
        usb.relays = []
    if change == "relay":
        next(iter(usb.relays.values())).state = lambda: None
    if change == "helper":
        arguments["helpers"] = {}
    if change == "wrapper":
        previous = usb.on_api_get

        @functools.wraps(previous)
        def foreign(*args, **kwargs):
            return previous(*args, **kwargs)

        usb.on_api_get = foreign
    before = dict(vars(usb))
    assert not check(usb, **arguments).compatible
    assert vars(usb) == before
