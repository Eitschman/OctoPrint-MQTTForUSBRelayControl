"""Check the project listing with the unmodified official registry validator."""

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet

ROOT = Path(__file__).resolve().parents[1]


def metadata_errors(data, project, plugin_source):
    errors = []
    identifiers = list(project["entry-points"]["octoprint.plugin"])
    if identifiers != [data.get("id")]:
        errors.append("Registry identifier does not match the package entry point")
    python = data.get("compatibility", {}).get("python", "")
    package_python = project["requires-python"]
    if not python or SpecifierSet(python) != SpecifierSet(package_python):
        errors.append("Registry Python requirement does not match the package")
    plugin_python = None
    for statement in ast.parse(plugin_source).body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__plugin_pythoncompat__"
            for target in statement.targets
        ):
            plugin_python = ast.literal_eval(statement.value)
    if plugin_python is None or SpecifierSet(plugin_python) != SpecifierSet(package_python):
        errors.append("OctoPrint Python compatibility does not match the package")
    if data.get("license") != project.get("license"):
        errors.append("Registry license does not match the package")
    if "ai-developed" not in data.get("attributes", []):
        errors.append("The required AI development disclosure is missing")
    authors = [author["name"] for author in project.get("authors", [])]
    registry_authors = data.get("authors", [data.get("author")])
    if authors != registry_authors:
        errors.append("Registry authors do not match the package")
    return errors


def main():
    import frontmatter

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "entry", nargs="?", type=Path, default=ROOT / "extras/mqttforusbrelaycontrol.md"
    )
    parser.add_argument(
        "--validator",
        type=Path,
        default=ROOT / "artifacts/registry-validator/validate_front_matter.py",
    )
    arguments = parser.parse_args()
    contract = json.loads((ROOT / "tests/fixtures/registry-validator.json").read_text())
    if hashlib.sha256(arguments.validator.read_bytes()).hexdigest() != contract["sha256"]:
        raise ValueError("The official validator checksum changed; review before updating")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    data = frontmatter.load(arguments.entry).metadata
    plugin_source = (ROOT / "octoprint_mqttforusbrelaycontrol/__init__.py").read_text()
    errors = metadata_errors(data, project, plugin_source)
    for key in ("featuredimage",):
        image = data.get(key)
        if image and image.startswith("/assets/"):
            if not (arguments.entry.parent / image.lstrip("/")).is_file():
                errors.append("A registry image is missing from the local bundle")
    for image in data.get("screenshots", []):
        location = image["url"]
        if location.startswith("/assets/"):
            if not (arguments.entry.parent / location.lstrip("/")).is_file():
                errors.append("A registry screenshot is missing from the local bundle")
    if errors:
        raise ValueError("; ".join(errors))
    subprocess.run(
        [
            sys.executable,
            str(arguments.validator),
            str(arguments.entry.resolve()),
            "--src",
            str(arguments.entry.resolve().parent),
            "--debug",
            "--check-internal-assets",
            "--check-id-match",
            "--check-asset-match",
            "--check-py3-compat",
            "--action-output",
        ],
        check=True,
    )
    print("Project registry metadata matches the package and passes the official validator")
    print("Public URLs, release date, screenshots and human review still require release checks")


if __name__ == "__main__":
    main()
