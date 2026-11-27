"""Install exact upstream revisions into the currently selected test interpreter."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mqtt-version", choices=("0.8.19", "0.8.20"), default="0.8.20")
    arguments = parser.parse_args()
    manifest = json.loads((ROOT / "tests/fixtures/upstream-manifest.json").read_text())
    archives = []
    for prefix in ("usbrelay/", f"mqtt-{arguments.mqtt_version}/"):
        entry = next(item for item in manifest["files"] if item["path"].startswith(prefix))
        parts = entry["url"].split("/")
        owner, repository = parts[3:5]
        archives.append(f"https://github.com/{owner}/{repository}/archive/{entry['revision']}.zip")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-build-isolation", "--no-deps", *archives],
        check=True,
    )


if __name__ == "__main__":
    main()
