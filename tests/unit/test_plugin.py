"""Settings validation, authorization and persistent identity failures."""

import copy
import logging
from unittest.mock import Mock
from uuid import uuid4

import flask
import pytest
from werkzeug.exceptions import Forbidden

from octoprint_mqttforusbrelaycontrol import __plugin_load__
from octoprint_mqttforusbrelaycontrol.constants import DEFAULTS
from octoprint_mqttforusbrelaycontrol.plugin import MQTTForUSBRelayControlPlugin, validate_settings
from tests.upstream import Settings


@pytest.mark.parametrize(
    "data",
    [
        {"integration_enabled": 1},
        {"unexpected": True},
        {"instance_uuid": str(uuid4())},
        {"relays": []},
        {"relays": {"test": {"enabled": 1}}},
        {"relays": {"test": {"entity_type": "cover"}}},
        {"relays": {"test": {"display_name": "x" * 129}}},
        {"mqtt_prefix": "test/#"},
        {"discovery_prefix": ""},
        {"ha_birth_topic": "test//status"},
        {"device_name": 1},
        {"ha_birth_payload": "x" * 129},
        {"use_octoprint_device": 1},
        {"device_identifier": None},
        {"device_identifier": []},
        {"device_identifier": " "},
        {"device_identifier": " leading"},
        {"device_identifier": "trailing "},
        {"device_identifier": "control\x00character"},
        {"device_identifier": "x" * 129},
    ],
)
def test_v13_invalid_settings_are_english_and_rejected(data):
    with pytest.raises(ValueError):
        validate_settings(data, "")


def test_settings_uuid_is_read_only_and_input_not_mutated():
    identity = str(uuid4())
    data = {"instance_uuid": identity, "integration_enabled": True}
    assert validate_settings(data, identity) == {"integration_enabled": True}
    assert data["instance_uuid"] == identity


@pytest.mark.parametrize("identifier", ["", "ABC123", "Custom-device-ID"])
def test_device_grouping_settings_are_additive_and_preserve_identifier_case(identifier):
    data = {"use_octoprint_device": False, "device_identifier": identifier}
    assert validate_settings(data, "") == data
    assert DEFAULTS["use_octoprint_device"] is True
    assert DEFAULTS["device_identifier"] == ""


def test_v09_migration_never_rewrites_identity_or_discovery_ownership():
    plugin = instance()
    before = copy.deepcopy(plugin._settings.data)
    plugin.on_settings_migrate(1, None)
    plugin.on_settings_migrate(1, 1)
    with pytest.raises(ValueError, match="Unsupported"):
        plugin.on_settings_migrate(1, 2)
    assert plugin._settings.data == before


def instance():
    plugin = MQTTForUSBRelayControlPlugin()
    plugin._settings = Settings(copy.deepcopy(DEFAULTS))
    plugin._logger = logging.getLogger("test.plugin")
    plugin._plugin_manager = Mock()
    plugin.get_plugin_data_folder = Mock(return_value="artifacts/unit-plugin-data")
    return plugin


def test_identity_saved_once_and_failure_gates_runtime():
    plugin = instance()
    plugin._settings.save = Mock()
    plugin.initialize()
    plugin.initialize()
    assert plugin.identity_ready
    plugin._settings.save.assert_called_once_with(force=True)
    plugin = instance()
    plugin._settings.save = Mock(side_effect=OSError())
    plugin.initialize()
    plugin.on_after_startup()
    assert not plugin.identity_ready and plugin.runtime is None
    assert plugin._settings.get(["instance_uuid"]) == ""
    plugin.initialize()
    assert not plugin.identity_ready
    assert plugin._settings.save.call_count == 2


def test_s01_own_settings_save_has_no_original_calls():
    plugin = instance()
    plugin.runtime = Mock()
    plugin.on_settings_save({"integration_enabled": True})
    assert plugin._settings.get(["integration_enabled"]) is True
    plugin.runtime.invalidate.assert_called_once()


def test_grouping_settings_save_persists_only_own_configuration():
    plugin = instance()
    plugin.on_settings_save({"use_octoprint_device": False, "device_identifier": "Custom-ID"})
    assert plugin._settings.get(["use_octoprint_device"]) is False
    assert plugin._settings.get(["device_identifier"]) == "Custom-ID"
    plugin._plugin_manager.get_plugin_info.assert_not_called()


def test_admin_api_checks_permission_and_actions(monkeypatch):
    import octoprint_mqttforusbrelaycontrol.plugin as module

    plugin = instance()
    plugin.runtime = Mock()
    plugin.runtime.status.return_value = {"ready": False}
    permission = Mock(return_value=False)
    monkeypatch.setattr(module.Permissions.ADMIN, "can", permission)
    with flask.Flask(__name__).test_request_context():
        with pytest.raises(Forbidden):
            plugin.on_api_get(None)
        permission.return_value = True
        assert plugin.on_api_get(None).json == {"ready": False}
        assert plugin.on_api_command("resync", {}).json == {"accepted": True}
        plugin.runtime.worker.request.assert_called_once_with("resync")
        assert plugin.on_api_command("frontend", {"compatible": False}).json["accepted"]
    assert plugin.is_api_protected() and plugin.is_api_adminonly()
    assert plugin.get_update_information()["mqttforusbrelaycontrol"]["user"] == "Eitschman"
    assert plugin.is_template_autoescaped()


def test_load_entry_point_metadata_and_assets():
    import octoprint_mqttforusbrelaycontrol as module

    __plugin_load__()
    assert isinstance(module.__plugin_implementation__, MQTTForUSBRelayControlPlugin)
    assert module.__plugin_implementation__.get_assets()["js"]
    assert module.__plugin_implementation__.get_template_configs()[0]["custom_bindings"]
