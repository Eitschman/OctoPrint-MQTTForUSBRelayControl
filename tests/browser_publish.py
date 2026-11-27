"""Send one non-retained command to the explicitly generated loopback test broker."""

import os
import sys
import threading

import paho.mqtt.client as mqtt


def main():
    port = int(os.environ["TEST_BROKER_PORT"])
    topic = os.environ["TEST_COMMAND_TOPIC"]
    if (
        not 1024 <= port <= 65535
        or not topic.startswith("isolated/usbrelay/")
        or not topic.endswith("/set")
    ):
        raise ValueError("Invalid disposable broker target")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    received = threading.Event()
    if sys.argv[1:] == ["--expect-off"]:
        state_topic = topic.rsplit("/", 1)[0] + "/state"
        client.on_connect = lambda client, *args: client.subscribe(state_topic)
        client.on_message = (
            lambda client, userdata, message: received.set()
            if message.topic == state_topic and message.payload == b"OFF"
            else None
        )
    client.connect("127.0.0.1", port)
    client.loop_start()
    try:
        if sys.argv[1:] == ["--expect-off"]:
            if not received.wait(10):
                raise AssertionError(
                    "The original UI write did not produce the verified broker state"
                )
        else:
            client.publish(topic, "ON", qos=1, retain=False).wait_for_publish(timeout=5)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
