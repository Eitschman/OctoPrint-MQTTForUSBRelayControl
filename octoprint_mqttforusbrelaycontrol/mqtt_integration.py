"""Existing OctoPrint-MQTT helpers, concrete topics and owned subscriptions."""

import json


def concrete_topic(value):
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 65535:
        raise ValueError("A non-empty concrete MQTT topic is required")
    if any(character in value for character in ("+", "#", "\x00")) or any(
        not part for part in value.split("/")
    ):
        raise ValueError("MQTT topics must have non-empty segments and no wildcards")
    return value


def topic_prefix(value):
    if not isinstance(value, str):
        raise ValueError("MQTT prefix must be text")
    return concrete_topic(value.rstrip("/"))


def relay_topics(prefix, instance_uuid, entry):
    base = f"{topic_prefix(prefix)}/usbrelay/{instance_uuid}/{entry.vendor}-{entry.product}/{entry.channel}"
    return {name: concrete_topic(f"{base}/{name}") for name in ("set", "state", "availability")}


def mqtt_requirements(settings):
    active = settings.get_boolean(["publish", "lwActive"])
    suffix = settings.get(["publish", "lwTopic"])
    base = settings.get(["publish", "baseTopic"])
    if not active or not suffix:
        raise ValueError("Enable the Last Will in OctoPrint-MQTT for reliable availability")
    # Read leaves: PluginSettings.get on a dictionary does not merge defaults by default.
    lwt = concrete_topic(str(base or "") + str(suffix))
    prefix = topic_prefix(base or "")
    return prefix, lwt


def command_payload(payload):
    if isinstance(payload, bytes):
        if len(payload) > 3:
            return None
        try:
            payload = payload.decode("ascii")
        except UnicodeError:
            return None
    if payload == "ON":
        return True
    if payload == "OFF":
        return False
    return None


class MQTTIntegration:
    def __init__(self, helpers, diagnostic):
        self.helpers, self.diagnostic = helpers, diagnostic
        self.subscriptions = {}
        self.active = True
        self.submitted = 0
        self.failed = 0

    def publish(self, topic, payload):
        concrete_topic(topic)
        if not self.active:
            return False
        try:
            result = self.helpers["mqtt_publish"](
                topic,
                payload,
                retained=True,
                # Avoid Paho retransmission of unacknowledged historical QoS-1 states.
                qos=0,
                allow_queueing=False,
            )
        except Exception as error:
            self.failed += 1
            self.diagnostic(f"MQTT publish failed: {type(error).__name__}")
            return False
        if result is True:
            self.submitted += 1
            return True
        self.failed += 1
        return False

    def subscribe(self, topic, callback):
        concrete_topic(topic)
        if topic in self.subscriptions:
            return
        token = {"active": True}

        def receiver(actual_topic, payload, **metadata):
            if self.active and token["active"] and actual_topic == topic:
                try:
                    callback(actual_topic, payload, **metadata)
                except Exception as error:
                    self.diagnostic(f"MQTT callback failed: {type(error).__name__}")

        self.helpers["mqtt_subscribe"](topic, receiver)
        self.subscriptions[topic] = (receiver, token)

    def unsubscribe(self, topic):
        subscription = self.subscriptions.pop(topic, None)
        if subscription is None:
            return
        callback, token = subscription
        token["active"] = False
        try:
            self.helpers["mqtt_unsubscribe"](callback, topic=topic)
        except Exception as error:
            self.diagnostic(f"MQTT unsubscribe failed: {type(error).__name__}")

    def retain_subscriptions(self, desired):
        for topic in tuple(self.subscriptions):
            if topic not in desired:
                self.unsubscribe(topic)

    def close(self):
        self.active = False
        self.retain_subscriptions(set())

    @staticmethod
    def encoded(payload):
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
