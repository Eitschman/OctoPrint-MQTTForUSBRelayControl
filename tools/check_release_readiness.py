"""Fail closed until owner-approved public release information is present."""

import argparse
import json
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def release_blockers(root, evidence):
    blockers = []
    if not (root / "LICENSE").is_file():
        blockers.append("Owner-approved project license is missing")
    for key in (
        "license_approved",
        "identity_approved",
        "human_review",
        "hardware_tests",
        "beta_completed",
        "advisories_reviewed",
        "publication_authorized",
    ):
        if evidence.get(key) is not True:
            blockers.append(f"Release evidence is missing: {key}")
    version = evidence.get("version", "0.0.0.dev0")
    if Version(version).is_devrelease:
        blockers.append("A development snapshot is not a public release")
    for key in ("homepage", "source", "archive", "maintainer"):
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            blockers.append(f"Approved public metadata is missing: {key}")
    return blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    arguments = parser.parse_args()
    evidence = json.loads(arguments.evidence.read_text()) if arguments.evidence else {}
    blockers = release_blockers(ROOT, evidence)
    for blocker in blockers:
        print(blocker)
    raise SystemExit(1 if blockers else 0)


if __name__ == "__main__":
    main()
