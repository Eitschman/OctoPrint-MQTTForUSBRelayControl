"""Create a curated local source ZIP; this command never publishes anything."""

import argparse
import zipfile
from pathlib import Path

from check_artifact import check_entry, check_package, public_source_path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    arguments.destination.parent.mkdir(parents=True, exist_ok=True)
    names = []
    for candidate in ROOT.iterdir():
        if candidate.is_dir() and candidate.name not in {
            "octoprint_mqttforusbrelaycontrol",
            "tests",
            "tools",
            ".github",
            "docs",
        }:
            continue
        if candidate.is_dir():
            paths = (
                candidate.rglob("*")
                if candidate.name != "docs"
                else [
                    *candidate.glob("api-inventory.md"),
                    *candidate.glob("architecture.md"),
                    *candidate.glob("maintainer-guide.md"),
                    *candidate.glob("manual-test-plan.md"),
                    *candidate.glob("development-report.md"),
                    *candidate.glob("public/**/*"),
                    *candidate.glob("adr/**/*"),
                ]
            )
        else:
            paths = [candidate]
        for path in paths:
            name = path.relative_to(ROOT).as_posix()
            if not path.is_file() or not public_source_path(name):
                continue
            if path.is_symlink():
                raise ValueError("Public source cannot include symlinks")
            data = path.read_bytes()
            check_entry(name, data)
            names.append((name, data))
    with zipfile.ZipFile(arguments.destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(names):
            archive.writestr(f"OctoPrint-MQTTForUSBRelayControl/{name}", data)
    check_package(arguments.destination)
    print(f"Curated {len(names)} public source files; release approval is still required")


if __name__ == "__main__":
    main()
