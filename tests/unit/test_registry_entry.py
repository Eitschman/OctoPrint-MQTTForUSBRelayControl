"""Prevent registry declarations from drifting away from installable package metadata."""

import copy
import tomllib
from pathlib import Path

import pytest

from octoprint_mqttforusbrelaycontrol import __file__ as PLUGIN_PATH
from tools.validate_registry_entry import metadata_errors

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def metadata():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    data = {
        "id": "mqttforusbrelaycontrol",
        "author": "Eitschman",
        "license": "AGPL-3.0-or-later",
        "attributes": ["ai-developed"],
        "compatibility": {"python": ">=3.11"},
    }
    plugin = Path(PLUGIN_PATH).read_text()
    return data, project, plugin


def test_registry_matches_the_actual_installable_package(metadata):
    assert metadata_errors(*metadata) == []


@pytest.mark.parametrize("python", [">=3.9", ">=3.13", ""])
def test_registry_cannot_claim_different_python_support(metadata, python):
    data, project, plugin = metadata
    data["compatibility"]["python"] = python
    assert "Registry Python requirement does not match the package" in metadata_errors(
        data, project, plugin
    )


@pytest.mark.parametrize(
    "key,value",
    [("id", "foreign-plugin"), ("license", "MIT"), ("author", "Unapproved author"), ("attributes", [])],
)
def test_registry_cannot_change_project_identity_or_disclosures(metadata, key, value):
    data, project, plugin = copy.deepcopy(metadata)
    data[key] = value
    assert metadata_errors(data, project, plugin)


def test_octoprint_python_compatibility_cannot_drift_from_package(metadata):
    data, project, plugin = metadata
    plugin = plugin.replace('__plugin_pythoncompat__ = ">=3.11"', '__plugin_pythoncompat__ = ">=3.9"')
    assert "OctoPrint Python compatibility does not match the package" in metadata_errors(
        data, project, plugin
    )
