"""GitHub release metadata for the approved public companion repository."""

import re

from packaging.version import Version

from ._version import __version__
from .constants import IDENTIFIER

APPROVED_RELEASE_SOURCE = {
    "owner": "Eitschman",
    "repository": "OctoPrint-MQTTForUSBRelayControl",
    "prerelease": Version(__version__).is_prerelease,
}


def update_information(source=None):
    if source is None:
        return {}
    if not isinstance(source, dict) or set(source) != {"owner", "repository", "prerelease"}:
        raise ValueError("An explicitly approved release source is required")
    owner, repository = source["owner"], source["repository"]
    if (
        not isinstance(owner, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner)
        or repository != "OctoPrint-MQTTForUSBRelayControl"
        or type(source["prerelease"]) is not bool
    ):
        raise ValueError("Invalid companion release source")
    return {
        IDENTIFIER: {
            "displayName": "MQTT for USB Relay Control",
            "displayVersion": __version__,
            "type": "github_release",
            "user": owner,
            "repo": repository,
            "current": __version__,
            "release_compare": "python",
            "force_base": False,
            "prerelease": source["prerelease"],
            "pip": f"https://github.com/{owner}/{repository}/archive/{{target}}.zip",
        }
    }
