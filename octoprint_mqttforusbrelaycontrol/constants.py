"""Protocol and settings contracts."""

IDENTIFIER = "mqttforusbrelaycontrol"
SCHEMA_VERSION = 1
COMMAND_QUEUE_LIMIT = 128
COMMAND_MAX_AGE_SECONDS = 5.0
COMMAND_MIN_INTERVAL_SECONDS = 0.25
HARDWARE_WARNING_SECONDS = 2.0
DEFAULTS = {
    "integration_enabled": False,
    "discovery_enabled": True,
    "discovery_prefix": "homeassistant",
    "mqtt_prefix": "",
    "device_name": "",
    "use_octoprint_device": True,
    "device_identifier": "",
    "command_max_age": COMMAND_MAX_AGE_SECONDS,
    "command_min_interval": COMMAND_MIN_INTERVAL_SECONDS,
    "debug_logging": False,
    "instance_uuid": "",
    "ha_birth_topic": "homeassistant/status",
    "ha_birth_payload": "online",
    "relays": {},
}
SUPPORTED_USB_VERSIONS = {"1.0.0"}
SUPPORTED_MQTT_VERSIONS = {"0.8.19", "0.8.20"}
