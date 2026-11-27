"""Exercise registry output validation against the official RSS 2.0 feed shape."""

import json
import xml.etree.ElementTree as ET

import pytest

from tools.validate_registry_site import validate_site


@pytest.fixture
def site(tmp_path):
    entry = {
        "id": "mqttforusbrelaycontrol",
        "compatibility": {"python": ">=3.11"},
        "license": "AGPL-3.0-or-later",
        "author": "Eitschman",
        "attributes": ["ai-developed"],
    }
    (tmp_path / "plugins.json").write_text(json.dumps([entry]))
    (tmp_path / "notices.json").write_text("[]")
    (tmp_path / "search.json").write_text("{}")
    (tmp_path / "feed.xml").write_text(
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel><atom:link href="https://example.org/feed.xml" /></channel></rss>'
    )
    page = tmp_path / "plugins/mqttforusbrelaycontrol/index.html"
    page.parent.mkdir(parents=True)
    page.write_text("Synthetic plugin page")
    return tmp_path


def test_official_rss_feed_shape_is_accepted(site):
    validate_site(site)


def test_broken_xml_is_rejected(site):
    (site / "feed.xml").write_text('<rss version="2.0"><channel></rss>')
    with pytest.raises(ET.ParseError):
        validate_site(site)


def test_generated_registry_cannot_omit_the_project(site):
    (site / "plugins.json").write_text("[]")
    with pytest.raises(ValueError, match="exactly one"):
        validate_site(site)


def test_generated_registry_cannot_have_invalid_json_document_types(site):
    (site / "search.json").write_text("[]")
    with pytest.raises(ValueError, match="JSON type"):
        validate_site(site)
