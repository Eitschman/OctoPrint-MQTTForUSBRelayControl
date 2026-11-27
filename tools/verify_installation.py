"""Install local archives in fresh public-tool environments and run an isolated smoke test."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from check_artifact import check_package


def command(arguments, directory, environment):
    subprocess.run([str(value) for value in arguments], cwd=directory, env=environment, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Curated local source ZIP")
    parser.add_argument("--artifacts", nargs="+", required=True, type=Path)
    parser.add_argument("--python", default="3.13")
    parser.add_argument("--report", type=Path, default=Path("artifacts/installation-report.json"))
    arguments = parser.parse_args()
    source = arguments.source.resolve()
    check_package(source)
    artifacts = [path.resolve() for path in arguments.artifacts]
    for path in artifacts:
        check_package(path)
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("Install the public uv tool before running this verifier")
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith(("UV_", "PIP_")):
            environment.pop(key)
    for key in (
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "RUN_BROWSER_TESTS",
        "RUN_HA_TESTS",
    ):
        environment.pop(key, None)
    environment.update(
        UV_LINK_MODE="copy",
        UV_NO_CONFIG="1",
        PYTHONNOUSERSITE="1",
        PIP_CONFIG_FILE=os.devnull,
        PIP_INDEX_URL="https://pypi.org/simple",
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="relay-artifact-install-") as temporary:
        base = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(base / "source")
        harness = next((base / "source").iterdir())
        shutil.rmtree(harness / "octoprint_mqttforusbrelaycontrol")
        assert not (harness / "AGENTS.md").exists() and not (harness / "start-codex.sh").exists()
        for index, artifact in enumerate(artifacts):
            directory = base / f"environment-{index}"
            command([uv, "venv", directory, "--python", arguments.python], harness, environment)
            python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            command(
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    python,
                    artifact,
                    "OctoPrint==2.0.1",
                    "pytest==9.2.0",
                    "paho-mqtt==2.2.0",
                    "six==1.17.0",
                    "pip==26.3",
                    "setuptools>=77",
                    "wheel",
                ],
                harness,
                environment,
            )
            command(
                [
                    python,
                    "-c",
                    "from importlib.metadata import distribution; d=distribution('OctoPrint-MQTTForUSBRelayControl'); e=next(e for e in d.entry_points if e.group=='octoprint.plugin'); m=e.load(); m.__plugin_load__(); assert m.__plugin_pythoncompat__ == '>=3.9'; print('Installed entry point and assets are loadable')",
                ],
                harness,
                environment,
            )
            if index == 0:
                command([python, "tools/prepare_upstream.py"], harness, environment)
            command(
                [python, "tools/install_upstream.py", "--mqtt-version", "0.8.20"],
                harness,
                environment,
            )
            if index == 0:
                command(
                    [
                        python,
                        "-m",
                        "pytest",
                        "tests/unit",
                        "tests/integration/test_upstream_contracts.py",
                        "-q",
                    ],
                    harness,
                    environment,
                )
            environment["RUN_SERVICE_TESTS"] = "1"
            command(
                [
                    python,
                    "-m",
                    "pytest",
                    "tests/integration/test_services.py",
                    "tests/integration/test_missing_hardware.py",
                    "-q",
                ],
                harness,
                environment,
            )
            environment.pop("RUN_SERVICE_TESTS")
            command(
                [uv, "pip", "uninstall", "--python", python, "OctoPrint-MQTTForUSBRelayControl"],
                harness,
                environment,
            )
            command(
                [
                    python,
                    "-c",
                    "import importlib.util; assert importlib.util.find_spec('octoprint_mqttforusbrelaycontrol') is None; print('Companion uninstalled without source-tree fallback')",
                ],
                harness,
                environment,
            )
            results.append(
                {
                    "artifact": artifact.name,
                    "installed": True,
                    "entry_point": True,
                    "uninstalled": True,
                    "isolated_smoke": True,
                }
            )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Verified installation and removal of {len(results)} local archive formats")


if __name__ == "__main__":
    main()
