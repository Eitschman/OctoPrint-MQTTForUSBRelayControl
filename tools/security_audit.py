"""Compare complete installed PyPI inventories before and after adding the companion."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "octoprint-mqttforusbrelaycontrol"
SOURCE_PROJECTS = {"octoprint-usbrelaycontrol": "1.0.0"}
AUDITOR = "pip-audit==2.10.1"


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def inventory(python, environment):
    # Isolated mode excludes checkout metadata and user site-packages from discovery.
    code = (
        "import importlib.metadata as m,json,platform; "
        "print(json.dumps({'python':platform.python_version(), 'packages':"
        "[{'name':d.metadata['Name'],'version':d.version} for d in m.distributions()]}))"
    )
    result = subprocess.run(
        [str(python), "-I", "-c", code], env=environment, check=True, capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    packages = {}
    for row in data["packages"]:
        name, version = row["name"], row["version"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not re.fullmatch(
            r"[A-Za-z0-9_.+!-]+", version
        ):
            raise ValueError("Invalid installed package metadata")
        name = canonical(name)
        if name in packages:
            raise ValueError(f"Duplicate installed package: {name}")
        packages[name] = version
    return {"python": data["python"], "packages": dict(sorted(packages.items()))}


def parse_audit(data, expected, returncode):
    """Reject failed, partial, skipped or differently scoped advisory scans."""
    if returncode not in (0, 1) or not isinstance(data, dict):
        raise ValueError("The advisory scanner did not produce a successful report")
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list) or data.get("fixes") != []:
        raise ValueError("Invalid advisory report structure")
    seen, findings = {}, []
    for row in dependencies:
        if not isinstance(row, dict) or row.get("skip_reason"):
            raise ValueError("An indexed dependency could not be audited")
        name, version, vulnerabilities = row.get("name"), row.get("version"), row.get("vulns")
        if not isinstance(name, str) or not isinstance(version, str) or not isinstance(
            vulnerabilities, list
        ):
            raise ValueError("Incomplete advisory dependency record")
        name = canonical(name)
        if name in seen:
            raise ValueError("Duplicate advisory dependency record")
        seen[name] = version
        for vulnerability in vulnerabilities:
            identifier = vulnerability.get("id")
            aliases, fixes = vulnerability.get("aliases"), vulnerability.get("fix_versions")
            if (
                not isinstance(identifier, str)
                or not identifier
                or not isinstance(aliases, list)
                or not isinstance(fixes, list)
                or not all(isinstance(value, str) and value for value in aliases + fixes)
            ):
                raise ValueError("Incomplete advisory finding")
            findings.append(
                {"name": name, "version": version, "ids": sorted({identifier, *aliases}),
                 "fix_versions": sorted(set(fixes))}
            )
    if seen != expected:
        raise ValueError("Advisory inventory does not match the installed environment")
    if returncode != int(bool(findings)):
        raise ValueError("Advisory exit status contradicts the report")
    return findings


def compare(baseline, companion, baseline_findings, companion_findings):
    """Group aliases transitively, retaining package versions and complete provenance."""
    if baseline["python"] != companion["python"] or PROJECT in baseline["packages"]:
        raise ValueError("The baseline interpreter or companion isolation is invalid")
    if PROJECT not in companion["packages"]:
        raise ValueError("The companion was not installed")
    for name, version in baseline["packages"].items():
        if companion["packages"].get(name) != version:
            raise ValueError(f"The companion changed a baseline package: {name}")
    groups = []
    for source, findings in (("baseline", baseline_findings), ("companion", companion_findings)):
        for finding in findings:
            group = {**finding, "ids": set(finding["ids"]),
                     "fix_versions": set(finding["fix_versions"]), "sources": {source}}
            # Repeat because merging an alias set can connect previously separate groups.
            merged = True
            while merged:
                merged = False
                for existing in list(groups):
                    if (existing["name"], existing["version"]) == (group["name"], group["version"]) and existing["ids"] & group["ids"]:
                        for key in ("ids", "fix_versions", "sources"):
                            group[key].update(existing[key])
                        groups.remove(existing)
                        merged = True
            groups.append(group)
    result = []
    for group in groups:
        result.append({key: sorted(value) if isinstance(value, set) else value for key, value in group.items()})
    return sorted(result, key=lambda row: (row["name"], row["version"], row["ids"]))


def audit(inventoried, source_projects, output, environment):
    expected = {name: version for name, version in inventoried["packages"].items() if name not in source_projects}
    requirements = output.with_suffix(".requirements.txt")
    requirements.write_text("".join(f"{name}=={version}\n" for name, version in expected.items()), encoding="utf-8")
    # --no-deps audits the already resolved, complete inventory; installations always resolve dependencies.
    command = ["uvx", "--python", "3.13", AUDITOR, "--strict", "--progress-spinner", "off",
               "--no-deps", "--disable-pip", "-r", str(requirements), "-f", "json", "-o", str(output)]
    process = subprocess.run(command, env=environment, timeout=600, check=False)
    data = json.loads(output.read_text(encoding="utf-8"))
    return parse_audit(data, expected, process.returncode)


def summary(report):
    findings = report["findings"]
    added = [row for row in findings if row["sources"] == ["companion"]]
    inherited = [row for row in findings if "baseline" in row["sources"]]
    lines = ["## Plugin dependency security comparison", "",
             f"Python {report['baseline']['python']}; OctoPrint {report['octoprint']}; MQTT {report['mqtt']}.", "",
             f"**Additional known findings: {len(added)}. Baseline findings: {len(inherited)}.**", "",
             "A passing comparison does not certify the host or third-party plugins as secure.", "",
             "Source-only projects are not indexed by PyPI's advisory service:"]
    lines += [f"- `{name}=={version}`" for name, version in report["source_projects"].items()]
    lines += ["", "The companion runtime is checked separately with Bandit and authorization/command tests.", "",
              "| Package | Advisory IDs (aliases grouped) | Reported fixes | Origin |",
              "| --- | --- | --- | --- |"]
    for row in findings:
        ids = ", ".join(row["ids"])
        origin = "baseline" if "baseline" in row["sources"] else "ADDED BY COMPANION"
        lines.append(f"| {row['name']} {row['version']} | {ids} | {', '.join(row['fix_versions']) or 'none reported'} | {origin} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", choices=("3.11", "3.13"), required=True)
    parser.add_argument("--octoprint", choices=("2.0.1", "2.0.2"), required=True)
    parser.add_argument("--mqtt", choices=("0.8.19", "0.8.20"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Use an empty audit output directory to prevent stale reports")
    if not shutil.which("uv"):
        raise RuntimeError("Install the public uv tool before running the audit")
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("UV_", "PIP_")) and key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
    environment.update(UV_NO_CONFIG="1", UV_LINK_MODE="copy", PYTHONNOUSERSITE="1",
                       PIP_CONFIG_FILE=os.devnull, PIP_INDEX_URL="https://pypi.org/simple")
    manifest = json.loads((ROOT / "tests/fixtures/upstream-manifest.json").read_text())
    archives = []
    for prefix in ("usbrelay/", f"mqtt-{arguments.mqtt}/"):
        entry = next(row for row in manifest["files"] if row["path"].startswith(prefix))
        owner, repository = entry["url"].split("/")[3:5]
        archives.append(f"https://github.com/{owner}/{repository}/archive/{entry['revision']}.zip")
    source_projects = {**SOURCE_PROJECTS, "octoprint-mqtt": arguments.mqtt}
    with tempfile.TemporaryDirectory(prefix="relay-security-") as temporary:
        directory = Path(temporary)
        venv = directory / "environment"
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        def run(*values):
            subprocess.run([str(value) for value in values], env=environment, cwd=directory,
                           check=True, timeout=900)

        run("uv", "venv", "--python", arguments.python, venv)
        install = ("uv", "pip", "install", "--python", python)
        run(*install, f"OctoPrint=={arguments.octoprint}", "setuptools", "wheel", "pip==26.3")
        # The legacy upstream setup imports OctoPrint's build helper from this host.
        run(*install, "--no-build-isolation", *archives)
        run("uv", "pip", "check", "--python", python)
        baseline = inventory(python, environment)
        if baseline["packages"].get("octoprint") != arguments.octoprint or PROJECT in baseline["packages"]:
            raise ValueError("The baseline does not match the requested official host")
        if not baseline["python"].startswith(arguments.python + "."):
            raise ValueError("The baseline does not match the requested interpreter")
        for name, version in source_projects.items():
            if baseline["packages"].get(name) != version:
                raise ValueError(f"Unexpected source-only project version: {name}")
        baseline_findings = audit(baseline, source_projects, output / "baseline-audit.json", environment)
        run("uv", "build", "--wheel", "--python", arguments.python, "--out-dir", directory / "dist", ROOT)
        wheels = list((directory / "dist").glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("Expected exactly one companion wheel")
        wheel = wheels[0]
        run(*install, wheel)
        run("uv", "pip", "check", "--python", python)
        companion = inventory(python, environment)
        source_projects[PROJECT] = companion["packages"][PROJECT]
        companion_findings = audit(companion, source_projects, output / "companion-audit.json", environment)
        findings = compare(baseline, companion, baseline_findings, companion_findings)
        report = {"schema": 1, "checked_at": datetime.now(UTC).isoformat(), "auditor": AUDITOR,
                  "octoprint": arguments.octoprint, "mqtt": arguments.mqtt,
                  "baseline": baseline, "companion": companion, "source_projects": source_projects,
                  "upstream_archives": archives, "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                  "findings": findings}
        (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        rendered = summary(report)
        (output / "summary.md").write_text(rendered, encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
                stream.write(rendered)
        print(rendered)
        if any(row["sources"] == ["companion"] for row in findings):
            raise SystemExit("The companion introduced additional known dependency vulnerabilities")


if __name__ == "__main__":
    main()
