"""Fail closed until owner-approved public release information is present."""

import argparse
import json
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def release_blockers(root, evidence, stage="stable"):
    if stage not in ("beta", "stable"):
        raise ValueError("Unknown release stage")
    blockers = []
    if not (root / "LICENSE").is_file():
        blockers.append("Owner-approved project license is missing")
    for key in (
        "license_approved",
        "identity_approved",
        "human_review",
        "hardware_tests",
        "advisories_reviewed",
        "publication_authorized",
    ):
        if evidence.get(key) is not True:
            blockers.append(f"Release evidence is missing: {key}")
    if stage == "stable" and evidence.get("beta_completed") is not True:
        blockers.append("Release evidence is missing: beta_completed")
    version = Version(evidence.get("version", "0.0.0.dev0"))
    if version.is_devrelease:
        blockers.append("A development snapshot is not a public release")
    elif stage == "beta" and not version.is_prerelease:
        blockers.append("A beta release must use a prerelease version")
    elif stage == "stable" and version.is_prerelease:
        blockers.append("A stable release must not use a prerelease version")
    for key in ("homepage", "source", "archive", "maintainer"):
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            blockers.append(f"Approved public metadata is missing: {key}")
    return blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--stage", choices=("beta", "stable"), default="stable")
    arguments = parser.parse_args()
    evidence = json.loads(arguments.evidence.read_text()) if arguments.evidence else {}
    blockers = release_blockers(ROOT, evidence, arguments.stage)
    for blocker in blockers:
        print(blocker)
    raise SystemExit(1 if blockers else 0)


if __name__ == "__main__":
    main()
