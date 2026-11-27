"""Write dependency license declarations without paths, authors or credentials."""

import argparse
import importlib.metadata
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--node-metadata", type=Path, help="Optional local pnpm licenses list --json output"
    )
    arguments = parser.parse_args()
    python = []
    for distribution in importlib.metadata.distributions():
        metadata = distribution.metadata
        if metadata.get("Name", "").lower() == "octoprint-mqttforusbrelaycontrol":
            continue
        python.append(
            {
                "name": metadata.get("Name"),
                "version": distribution.version,
                "license_expression": metadata.get("License-Expression"),
                "license_classifiers": [
                    value
                    for value in metadata.get_all("Classifier", [])
                    if value.startswith("License ::")
                ],
                "license_declared": (metadata.get("License") or "").splitlines()[:1],
            }
        )
    node = []
    if arguments.node_metadata:
        for rows in json.loads(arguments.node_metadata.read_text()).values():
            for row in rows:
                node.append({key: row.get(key) for key in ("name", "versions", "license")})
    result = {
        "notice": "Upstream license metadata is not a legal compatibility approval",
        "python": sorted(python, key=lambda row: row["name"].lower()),
        "node": node,
    }
    arguments.destination.parent.mkdir(parents=True, exist_ok=True)
    arguments.destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Inventoried {len(python)} Python distributions and {len(node)} Node packages")


if __name__ == "__main__":
    main()
