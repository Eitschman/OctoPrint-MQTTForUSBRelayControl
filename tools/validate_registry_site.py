"""Validate official registry build outputs and the generated project listing."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def validate_site(directory):
    documents = {}
    for name, expected in (("plugins.json", list), ("notices.json", list), ("search.json", dict)):
        documents[name] = json.loads((directory / name).read_text())
        if not isinstance(documents[name], expected):
            raise ValueError(f"The generated {name} has an unexpected JSON type")
    feed = ET.parse(directory / "feed.xml")
    if feed.getroot().tag != "{http://www.w3.org/2005/Atom}feed":
        raise ValueError("The generated feed is not an Atom feed")
    entries = [
        entry for entry in documents["plugins.json"] if entry.get("id") == "mqttforusbrelaycontrol"
    ]
    if len(entries) != 1:
        raise ValueError("The generated registry must contain exactly one project entry")
    entry = entries[0]
    if entry["compatibility"]["python"] != ">=3.11":
        raise ValueError("The generated Python compatibility does not match the project")
    if entry["license"] != "AGPL-3.0-or-later" or entry["author"] != "Eitschman":
        raise ValueError("The generated license or maintainer does not match approved metadata")
    if "ai-developed" not in entry["attributes"]:
        raise ValueError("The generated registry lost the AI development disclosure")
    if not (directory / "plugins/mqttforusbrelaycontrol/index.html").is_file():
        raise ValueError("The generated plugin page is missing")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    validate_site(arguments.directory)
    print("Official Jekyll output: JSON documents, Atom feed and project listing passed")


if __name__ == "__main__":
    main()
