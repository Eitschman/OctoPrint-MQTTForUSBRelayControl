"""Release metadata and the installed OctoPrint release-selection contract."""

from unittest.mock import Mock

import pytest
from octoprint.plugins.softwareupdate.version_checks import github_release
from packaging.version import Version

from octoprint_mqttforusbrelaycontrol.constants import IDENTIFIER
from octoprint_mqttforusbrelaycontrol.updates import update_information


def test_v08_pep440_and_actual_updater_channel_selection():
    versions = ["0.1.0.dev0", "0.1.0-alpha.1", "0.1.0-beta.1", "0.1.0-rc.1", "0.1.0"]
    assert sorted(map(Version, reversed(versions))) == list(map(Version, versions))
    comparable = github_release._get_comparable_factory("python", force_base=False)
    releases = [
        dict(
            name=value,
            tag_name=str(Version(value)),
            prerelease=Version(value).is_prerelease,
            draft=Version(value).is_devrelease,
            target_commitish="test",
        )
        for value in versions[:-1]
    ]
    stable = dict(
        name="0.0.9", tag_name="0.0.9", prerelease=False, draft=False, target_commitish="main"
    )
    releases.append(stable)

    def key(release):
        return comparable(release["tag_name"])

    assert github_release._filter_out_latest(releases, sort_key=key)[1] == "0.0.9"
    assert (
        github_release._filter_out_latest(releases, sort_key=key, include_prerelease=True)[1]
        == "0.1.0rc1"
    )


def test_v09_inactive_and_explicit_source_offline_contract(monkeypatch):
    assert update_information() == {}
    source = {
        "owner": "synthetic-maintainer",
        "repository": "OctoPrint-MQTTForUSBRelayControl",
        "prerelease": False,
    }
    configuration = update_information(source)[IDENTIFIER]
    assert configuration["pip"].endswith("/OctoPrint-MQTTForUSBRelayControl/archive/{target}.zip")
    network = Mock(side_effect=AssertionError("No network in an offline update check"))
    monkeypatch.setattr(github_release, "_get_latest_release", network)
    information, current = github_release.get_latest(IDENTIFIER, configuration, online=False)
    assert current and information["remote"]["value"] == "?"
    network.assert_not_called()
    for invalid in (
        {},
        dict(source, repository="OctoPrint-MQTT"),
        dict(source, owner="../foreign"),
        dict(source, prerelease="false"),
    ):
        with pytest.raises(ValueError):
            update_information(invalid)


def test_v09_upstream_handles_unreachable_and_incomplete_release_response(monkeypatch):
    import requests
    from octoprint.plugins.softwareupdate import version_checks
    from octoprint.plugins.softwareupdate.exceptions import NetworkError

    response = Mock()
    response.json.return_value = [{"tag_name": "incomplete"}]
    monkeypatch.setattr(github_release.requests, "get", Mock(return_value=response))
    monkeypatch.setattr(version_checks, "check_github_apiresponse", lambda *args: None)
    monkeypatch.setattr(version_checks, "check_github_ratelimit", lambda *args: None)
    assert github_release._get_latest_release("synthetic", "synthetic", "python") == (
        None,
        None,
        None,
    )
    monkeypatch.setattr(
        github_release.requests, "get", Mock(side_effect=requests.ConnectionError())
    )
    with pytest.raises(NetworkError):
        github_release._get_latest_release("synthetic", "synthetic", "python")
