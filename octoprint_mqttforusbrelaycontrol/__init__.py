"""Event-driven companion for existing USB Relay Control and MQTT plugins."""

from typing import Any

from ._version import __version__

__plugin_name__ = "MQTT for USB Relay Control"
__plugin_author__ = "Eitschman"
__plugin_license__ = "AGPL-3.0-or-later"
__plugin_url__ = "https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl"
__plugin_version__ = __version__
__plugin_pythoncompat__ = ">=3.11"
__plugin_implementation__: Any = None
__plugin_hooks__: dict[str, Any] = {}


def __plugin_load__():
    from .plugin import MQTTForUSBRelayControlPlugin

    global __plugin_implementation__, __plugin_hooks__
    __plugin_implementation__ = MQTTForUSBRelayControlPlugin()
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    }
