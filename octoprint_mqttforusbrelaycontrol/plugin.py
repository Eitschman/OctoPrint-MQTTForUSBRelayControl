"""OctoPrint mixins and the authenticated companion settings API."""

import copy
from uuid import UUID, uuid4

import flask
import octoprint.plugin
from octoprint.access.permissions import Permissions

from ._version import __version__
from .command_settings import COMMAND_TIMING_RANGES, validate_command_timing
from .constants import DEFAULTS, IDENTIFIER
from .discovery import valid_device_identifier
from .lifecycle import RelayRuntime
from .mqtt_integration import concrete_topic, topic_prefix
from .updates import APPROVED_RELEASE_SOURCE, update_information


def validate_settings(data, current_uuid):
    if not isinstance(data, dict) or set(data) - set(DEFAULTS):
        raise ValueError("Unknown companion settings")
    result = copy.deepcopy(data)
    if "instance_uuid" in result and result.pop("instance_uuid") != current_uuid:
        raise ValueError("Use the confirmed offline clone action to change instance identity")
    for key in (
        "integration_enabled",
        "discovery_enabled",
        "debug_logging",
        "use_octoprint_device",
    ):
        if key in result and type(result[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    for key in ("device_name", "ha_birth_payload"):
        if key in result and (not isinstance(result[key], str) or len(result[key]) > 128):
            raise ValueError(f"{key} must be text of at most 128 characters")
    for key in COMMAND_TIMING_RANGES:
        if key in result:
            validate_command_timing(key, result[key])
    if "device_identifier" in result and result["device_identifier"] != "":
        if not valid_device_identifier(result["device_identifier"]):
            raise ValueError("Device identifier must be printable text of at most 128 characters")
    for key in ("discovery_prefix", "mqtt_prefix"):
        if key in result and (result[key] or key != "mqtt_prefix"):
            topic_prefix(result[key])
    if "ha_birth_topic" in result:
        concrete_topic(result["ha_birth_topic"])
    if "relays" in result:
        if not isinstance(result["relays"], dict) or len(result["relays"]) > 2048:
            raise ValueError("Relay settings must be a bounded object")
        for identity, row in result["relays"].items():
            if (
                not isinstance(identity, str)
                or len(identity) > 80
                or not isinstance(row, dict)
                or set(row) - {"enabled", "entity_type", "display_name"}
            ):
                raise ValueError("Invalid relay settings")
            if type(row.get("enabled", False)) is not bool or row.get(
                "entity_type", "switch"
            ) not in ("switch", "light", "fan"):
                raise ValueError("Invalid relay enable flag or entity type")
            if (
                not isinstance(row.get("display_name", ""), str)
                or len(row.get("display_name", "")) > 128
            ):
                raise ValueError("Relay display name must be text of at most 128 characters")
    return result


class MQTTForUSBRelayControlPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.RestartNeedingPlugin,
):
    def __init__(self):
        self.runtime = None
        self.identity_ready = False

    def get_settings_defaults(self):
        return copy.deepcopy(DEFAULTS)

    def get_settings_version(self):
        return 1

    def on_settings_migrate(self, target, current):
        # Version 1 is the first public settings contract; no legacy keys are invented.
        if current not in (None, 1):
            raise ValueError("Unsupported companion settings version")

    def initialize(self):
        try:
            identity = self._settings.get(["instance_uuid"])
            if identity:
                if str(UUID(identity)) != identity:
                    raise ValueError("Instance UUID must be canonical")
            else:
                identity = str(uuid4())
                self._settings.set(["instance_uuid"], identity)
                try:
                    self._settings.save(force=True)
                except Exception:
                    self._settings.set(["instance_uuid"], "")
                    raise
            self.identity_ready = True
            if self.runtime is None:
                self.runtime = RelayRuntime(
                    self._plugin_manager,
                    self._settings,
                    self.get_plugin_data_folder(),
                    self._logger,
                    self._send_status,
                )
                self.runtime.register_receiver()
        except Exception as error:
            self.identity_ready = False
            self._logger.error("Persistent instance identity unavailable: %s", type(error).__name__)

    def on_after_startup(self):
        if self.identity_ready and self.runtime:
            self.runtime.start()

    def _send_status(self, status):
        status["versions"][IDENTIFIER] = __version__
        self._plugin_manager.send_plugin_message(
            IDENTIFIER, status, permissions=[Permissions.SETTINGS_READ]
        )

    def on_settings_save(self, data):
        validated = validate_settings(data, self._settings.get(["instance_uuid"]))
        result = super().on_settings_save(validated)
        if self.runtime:
            self.runtime.invalidate()
            self.runtime.settings_updated()
        return result

    def on_event(self, event, payload):
        if self.runtime:
            self.runtime.on_event(event, payload)

    def on_shutdown(self):
        if self.runtime:
            self.runtime.stop()

    def on_plugin_disabled(self):
        self.on_shutdown()

    def on_plugin_pending_uninstall(self):
        self.on_shutdown()

    def get_assets(self):
        return {"js": ["js/mqttforusbrelaycontrol.js"], "css": ["css/mqttforusbrelaycontrol.css"]}

    def is_template_autoescaped(self):
        return True

    def get_template_configs(self):
        return [{"type": "settings", "custom_bindings": True, "name": "MQTT for USB Relay Control"}]

    def is_api_adminonly(self):
        return True

    def is_api_protected(self):
        return True

    def get_api_commands(self):
        return {
            "resync": [],
            "rediscover": [],
            "cleanup": ["confirmed"],
            "clone": ["confirmed"],
            "frontend": ["compatible"],
        }

    def _require_admin(self):
        if not Permissions.ADMIN.can():
            flask.abort(403, description="Administrator permission is required")
        if not self.runtime:
            flask.abort(503, description="Companion runtime is unavailable")
        return self.runtime

    def on_api_get(self, request):
        runtime = self._require_admin()
        return flask.jsonify(runtime.status())

    def on_api_command(self, command, data):
        runtime = self._require_admin()
        if command == "clone":
            try:
                identity = runtime.clone_identity(data.get("confirmed") is True)
            except ValueError as error:
                flask.abort(409, description=str(error))
            return flask.jsonify({"instance_uuid": identity})
        if command == "frontend":
            if type(data.get("compatible")) is not bool:
                flask.abort(400, description="Frontend compatibility must be boolean")
            runtime.frontend_compatible = data["compatible"]
        elif command in ("resync", "rediscover", "cleanup"):
            if command == "cleanup" and data.get("confirmed") is not True:
                flask.abort(400, description="Confirm submission of pending discovery deletions")
            runtime.worker.request(command)
        else:
            flask.abort(400, description="Unknown companion command")
        return flask.jsonify({"accepted": True})

    def get_update_information(self):
        # No public repository or release source has been approved yet.
        return update_information(APPROVED_RELEASE_SOURCE)
