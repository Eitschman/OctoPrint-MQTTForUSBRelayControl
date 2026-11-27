"""R01–R18: reproduce upstream boundaries, without claiming companion behavior."""

import ast
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from paho.mqtt.client import CallbackAPIVersion, Client

from tests.upstream import MQTT_METHODS, lifecycle_class, mqtt, original, relay_class, source

pytestmark = pytest.mark.integration


@pytest.fixture(params=["0.8.20", "0.8.19"])
def upstream_mqtt(request):
    return mqtt(request.param)


def test_r01_read_does_not_write():
    relay = relay_class()()
    assert relay.state(1) is False
    assert relay.state(1, None) is False
    assert relay.h.writes == []


def test_r02_negative_write_code_is_discarded():
    relay = relay_class()()
    relay.h.write_result = -1
    assert relay.state(1, True) is None
    assert relay.state(1) is False


def test_r03_empty_report_is_not_off():
    relay = relay_class()()
    relay.h.empty_report = True
    with pytest.raises(IndexError):
        relay.state(1)


def test_r04_original_exception_identity():
    relay = relay_class()()
    error = OSError("Synthetic write error")
    relay.h.write_error = error
    with pytest.raises(OSError) as caught:
        relay.state(1, True)
    assert caught.value is error


def test_r05_channel_zero_is_all_channels():
    relay = relay_class()()
    relay.state(0, True)
    assert relay.h.writes == [[0xFE]]
    assert relay.state(0) == [True] * 8


def test_r06_offline_publish_without_queue(upstream_mqtt):
    upstream_mqtt._mqtt_connected = False
    assert upstream_mqtt.mqtt_publish("test/state", "ON", allow_queueing=False) is False
    upstream_mqtt._mqtt.publish.assert_not_called()
    assert not upstream_mqtt._mqtt_publish_queue


def test_r07_helper_true_is_not_publish_ack(upstream_mqtt):
    upstream_mqtt._mqtt.publish.return_value = SimpleNamespace(rc=4)
    assert upstream_mqtt.mqtt_publish("test/state", "ON") is True


def test_r08_offline_queue_loses_retain(upstream_mqtt):
    upstream_mqtt._mqtt_connected = False
    upstream_mqtt.mqtt_publish("test/state", "ON", retained=False, allow_queueing=True)
    upstream_mqtt._on_mqtt_connect(upstream_mqtt._mqtt, None, None, 0)
    assert any(
        call.kwargs.get("retain") is True and call.args[0] == "test/state"
        for call in upstream_mqtt._mqtt.publish.call_args_list
    )


def test_r09_subscribe_has_no_qos_option(upstream_mqtt):
    assert "qos" not in inspect.signature(upstream_mqtt.mqtt_subscribe).parameters
    assert upstream_mqtt.mqtt_subscribe("test/set", Mock()) is None
    upstream_mqtt._mqtt.subscribe.assert_called_once_with("test/set")


def test_r10_topic_specific_unsubscribe(upstream_mqtt):
    callback = Mock()
    upstream_mqtt.mqtt_subscribe("test/one", callback)
    upstream_mqtt.mqtt_subscribe("test/two", callback)
    upstream_mqtt.mqtt_unsubscribe(callback, "test/one")
    upstream_mqtt._mqtt.unsubscribe.assert_called_once_with("test/one")
    assert [item[0] for item in upstream_mqtt._mqtt_subscriptions] == ["test/two"]


def test_r11_three_topics_expand_into_invalid_paho_arguments(upstream_mqtt):
    callback = Mock()
    for topic in ("test/one", "test/two", "test/three"):
        upstream_mqtt.mqtt_subscribe(topic, callback)
    upstream_mqtt._mqtt.unsubscribe = Client(CallbackAPIVersion.VERSION2).unsubscribe
    with pytest.raises(TypeError):
        upstream_mqtt.mqtt_unsubscribe(callback)


def test_r12_callback_receives_retained_metadata(upstream_mqtt):
    callback = Mock()
    upstream_mqtt.mqtt_subscribe("test/set", callback)
    upstream_mqtt._on_mqtt_message(
        upstream_mqtt._mqtt,
        None,
        SimpleNamespace(topic="test/set", payload=b"ON", retain=True, qos=0),
    )
    callback.assert_called_once_with("test/set", b"ON", retained=True, qos=0)


def test_r13_empty_string_is_distinct_from_json_object(upstream_mqtt):
    upstream_mqtt.mqtt_publish("test/config", {}, retained=True)
    upstream_mqtt.mqtt_publish("test/config", "", retained=True)
    assert [call.kwargs["payload"] for call in upstream_mqtt._mqtt.publish.call_args_list] == [
        "{}",
        "",
    ]


@pytest.mark.parametrize("mode, expected", [("active_high", True), ("active_low", False)])
def test_r14_active_mode_uses_original_api(mode, expected):
    plugin = original()
    plugin._settings.data["usbrelay_configurations"][0]["active_mode"] = mode
    plugin.on_after_startup()
    plugin.on_api_command("turnUSBRelayOn", {"id": 0})
    assert plugin.relays["16c0:05df"].state(1) is expected


def test_r15_original_save_recreates_objects_and_defaults():
    plugin = original()
    plugin.on_after_startup()
    old = plugin.relays["16c0:05df"]
    old.state(1, True)
    plugin.on_settings_save({})
    new = plugin.relays["16c0:05df"]
    assert new is not old and old.h.closed
    assert new.h.writes == [[0xFD, 1]]


def test_r16_primary_mqtt_methods_have_identical_ast():
    def methods(version):
        tree = ast.parse(source(f"mqtt-{version}/octoprint_mqtt/__init__.py"))
        cls = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MqttPlugin"
        )
        return {
            node.name: ast.dump(node)
            for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name in MQTT_METHODS - {"_get_topic"}
        }

    assert len(methods("0.8.20")) == 6
    assert methods("0.8.19") == methods("0.8.20")


def test_r17_two_topics_bind_second_to_properties(upstream_mqtt):
    callback = Mock()
    for topic in ("test/one", "test/two"):
        upstream_mqtt.mqtt_subscribe(topic, callback)
    client = Client(CallbackAPIVersion.VERSION2)
    client._sock = Mock()
    client._send_unsubscribe = Mock(return_value=0)
    upstream_mqtt._mqtt.unsubscribe = client.unsubscribe
    upstream_mqtt.mqtt_unsubscribe(callback)
    args = client._send_unsubscribe.call_args.args
    assert args[1] == [b"test/one"]
    assert args[2] == "test/two"


def test_r18_lifecycle_manager_is_not_automatically_attached():
    manager = SimpleNamespace(
        **{f"on_plugin_{name}": Mock() for name in ("loaded", "unloaded", "enabled", "disabled")}
    )
    lifecycle = lifecycle_class()(manager)
    callback = Mock()
    lifecycle.add_callback("enabled", callback)
    manager.on_plugin_enabled("test", None)
    callback.assert_not_called()
    lifecycle.on_plugin_event("enabled", "test", None)
    callback.assert_called_once_with("test", None)
