"""Opt-in installed-plugin and real broker integration; synthetic HID only."""

import json
import os
import threading

import paho.mqtt.client as mqtt
import pytest

from tests.services import IsolatedOctoPrint, broker, wait_for

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_SERVICE_TESTS") != "1",
        reason="Set RUN_SERVICE_TESTS=1 for disposable loopback services",
    ),
]


def test_i01_i02_installed_plugins_real_broker(tmp_path):
    control = {}
    with broker(tmp_path / "broker", control) as port:
        with IsolatedOctoPrint(tmp_path / "octoprint", port) as server:
            initial = wait_for(
                lambda: server.get("/api/plugin/mqttforusbrelaycontrol")
                if server.get("/api/plugin/mqttforusbrelaycontrol")["relays"]
                else None
            )
            assert initial["versions"]["mqtt"] in ("0.8.19", "0.8.20")
            identity = initial["relays"][0]["id"]
            wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["connected"] is True)
            server.post(
                "/api/settings",
                {
                    "plugins": {
                        "mqttforusbrelaycontrol": {
                            "integration_enabled": True,
                            "relays": {
                                identity: {
                                    "enabled": True,
                                    "entity_type": "switch",
                                    "display_name": "",
                                }
                            },
                        }
                    }
                },
            )
            status = wait_for(
                lambda: (
                    value
                    if (value := server.get("/api/plugin/mqttforusbrelaycontrol"))["ready"]
                    else None
                )
            )
            instance_uuid = server.get("/api/settings")["plugins"]["mqttforusbrelaycontrol"][
                "instance_uuid"
            ]
            base = f"isolated/usbrelay/{instance_uuid}/16c0-05df/1"
            messages = []
            connected = threading.Event()
            disconnected = threading.Event()
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

            def on_connect(client, userdata, flags, reason, properties):
                client.subscribe("isolated/#")
                client.subscribe("homeassistant/#")
                connected.set()

            client.on_connect = on_connect
            client.on_disconnect = lambda *args: disconnected.set()
            client.on_message = lambda client, userdata, message: messages.append(
                (message.topic, message.payload, message.retain)
            )
            client.connect("127.0.0.1", port)
            client.loop_start()
            try:
                assert connected.wait(5)
                client.publish(base + "/set", "ON", qos=1, retain=False).wait_for_publish(5)
                wait_for(
                    lambda: any(
                        topic == base + "/state" and payload == b"ON"
                        for topic, payload, _ in messages
                    )
                )
                status = server.get("/api/plugin/mqttforusbrelaycontrol")
                assert status["relays"][0]["snapshot"]["actual"] is True
                assert status["relays"][0]["snapshot"]["outcome"] == "confirmed"
                client.publish(base + "/set", "OFF", qos=1, retain=True).wait_for_publish(5)
                # A live retained publish arrives with retain=False to an existing subscriber.
                # Disable/re-enable to test broker replay with retain=True before any action.
                wait_for(
                    lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["relays"][0][
                        "snapshot"
                    ]["actual"]
                    is False
                )
                server.post(
                    "/api/settings",
                    {"plugins": {"mqttforusbrelaycontrol": {"integration_enabled": False}}},
                )
                wait_for(lambda: not server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
                client.publish(base + "/set", "ON", qos=1, retain=True).wait_for_publish(5)
                server.post(
                    "/api/settings",
                    {"plugins": {"mqttforusbrelaycontrol": {"integration_enabled": True}}},
                )
                wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
                retained_status = server.get("/api/plugin/mqttforusbrelaycontrol")
                assert retained_status["relays"][0]["snapshot"]["actual"] is False
                client.publish(base + "/set", "ON", qos=1, retain=False).wait_for_publish(5)
                wait_for(
                    lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["relays"][0][
                        "snapshot"
                    ]["actual"]
                    is True
                )
                server.post("/api/plugin/mqttforusbrelaycontrol", {"command": "resync"})
                assert server.get("/api/plugin/usbrelaycontrol") == ["on"]
                control["pause"]()
                assert disconnected.wait(5)
                wait_for(
                    lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["connected"] is False
                )
                server.post("/api/plugin/usbrelaycontrol", {"command": "turnUSBRelayOff", "id": 0})
                assert server.get("/api/plugin/usbrelaycontrol") == ["off"]
                messages.clear()
                control["restart"]()
                wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
                wait_for(
                    lambda: any(
                        topic == base + "/state" and payload == b"OFF"
                        for topic, payload, _ in messages
                    )
                )
                assert not any(
                    topic == base + "/state" and payload == b"ON" for topic, payload, _ in messages
                ), [
                    (topic, payload)
                    for topic, payload, _ in messages
                    if topic.endswith(("state", "set"))
                ]

                discovery_topic = f"homeassistant/switch/{identity}/config"
                discovery = wait_for(
                    lambda: next(
                        (
                            json.loads(payload)
                            for topic, payload, _ in messages
                            if topic == discovery_topic and payload
                        ),
                        None,
                    )
                )
                assert discovery["retain"] is False
                server.post(
                    "/api/settings",
                    {"plugins": {"mqttforusbrelaycontrol": {"integration_enabled": False}}},
                )
                wait_for(
                    lambda: any(
                        topic == discovery_topic and payload == b""
                        for topic, payload, _ in messages
                    )
                )
            finally:
                client.disconnect()
                client.loop_stop()


def test_review_dependency_disable_retires_retained_online_availability(tmp_path):
    with broker(tmp_path / "broker") as port:
        with IsolatedOctoPrint(tmp_path / "octoprint", port) as server:
            status = wait_for(
                lambda: value
                if (value := server.get("/api/plugin/mqttforusbrelaycontrol"))["relays"]
                else None
            )
            identity = status["relays"][0]["id"]
            server.post(
                "/api/settings",
                {
                    "plugins": {
                        "mqttforusbrelaycontrol": {
                            "integration_enabled": True,
                            "relays": {identity: {"enabled": True}},
                        }
                    }
                },
            )
            wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
            instance_uuid = server.get("/api/settings")["plugins"]["mqttforusbrelaycontrol"][
                "instance_uuid"
            ]
            topic = f"isolated/usbrelay/{instance_uuid}/16c0-05df/1/availability"
            messages = []
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_connect = lambda client, *args: client.subscribe(topic)
            client.on_message = lambda client, userdata, message: messages.append(
                (message.payload, message.retain)
            )
            client.connect("127.0.0.1", port)
            client.loop_start()
            try:
                # Subscription may race the initial publication and receive it live.
                wait_for(lambda: any(payload == b"online" for payload, _ in messages))
                server.post(
                    "/api/plugin/pluginmanager", {"command": "disable", "plugin": "usbrelaycontrol"}
                )
                wait_for(lambda: (b"offline", False) in messages)
                wait_for(lambda: not server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
                # A fresh subscriber must receive the new retained offline value.
                messages.clear()
                client.disconnect()
                client.loop_stop()
                client.connect("127.0.0.1", port)
                client.loop_start()
                wait_for(lambda: (b"offline", True) in messages)
                assert not any(payload == b"online" for payload, _ in messages)
            finally:
                client.disconnect()
                client.loop_stop()
