"""Run every Bandit check on all runtime Python files and verify complete coverage."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_scan(report, expected):
    metrics = report.get("metrics", {})
    scanned = {Path(name).resolve() for name in metrics if name != "_totals"}
    if report.get("errors") != [] or report.get("results") != [] or scanned != expected:
        raise ValueError("The runtime security scan has findings, errors or incomplete coverage")
    if metrics.get("_totals", {}).get("skipped_tests") != 0:
        raise ValueError("Runtime security checks were suppressed")
    if not expected or metrics.get("_totals", {}).get("loc", 0) <= 0:
        raise ValueError("The runtime security scan did not inspect source code")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/security/bandit.json"))
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Use a new report path to prevent stale scanner results")
    package = ROOT / "octoprint_mqttforusbrelaycontrol"
    # An explicit empty configuration prevents implicit user/project skip settings.
    with tempfile.TemporaryDirectory(prefix="relay-security-scan-") as temporary:
        configuration = Path(temporary) / "bandit.ini"
        configuration.write_text("[bandit]\n", encoding="utf-8")
        subprocess.run(["uvx", "--python", "3.13", "bandit==1.9.4", "-r", str(package),
                        "--ignore-nosec", "--ini", str(configuration), "-f", "json",
                        "-o", str(output)], check=True, timeout=600)
    validate_scan(json.loads(output.read_text(encoding="utf-8")), {path.resolve() for path in package.rglob("*.py")})
    print("All runtime Python files passed every Bandit check; no findings or exclusions")


if __name__ == "__main__":
    main()
