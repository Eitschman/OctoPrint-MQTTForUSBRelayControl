"""Inspect archive privacy, required assets and entry points independently of ignores."""

import argparse
import io
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

PRIVATE_NAMES = {
    "AGENTS.md",
    "start-codex.sh",
    "mqtt_for_usbrelay.md",
    "veroeffentlichung.md",
    ".env",
    "config.yaml",
    "users.yaml",
    "storage-state.json",
}
PRIVATE_PARTS = {
    ".git",
    ".svn",
    ".codex",
    ".agents",
    ".venv",
    ".ha",
    "artifacts",
    "node_modules",
    "__pycache__",
}
PRIVATE_MARKER = b"PRIVATE_" + b"DEVELOPMENT_CANARY"
PUBLIC_DIRECTORIES = {"octoprint_mqttforusbrelaycontrol", "tests", "tools", ".github"}
PUBLIC_FILES = {
    "docs/api-inventory.md",
    "docs/architecture.md",
    "docs/maintainer-guide.md",
    "docs/manual-test-plan.md",
    "docs/development-report.md",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
    "MANIFEST.in",
    "package.json",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "eslint.config.js",
    "vitest.config.ts",
    "playwright.config.ts",
    ".gitignore",
    "LICENSE",
}
REQUIRED_ASSETS = {
    "__init__.py",
    "_version.py",
    "static/js/mqttforusbrelaycontrol.js",
    "static/css/mqttforusbrelaycontrol.css",
    "templates/mqttforusbrelaycontrol_settings.jinja2",
    "translations/messages.pot",
    "translations/de/LC_MESSAGES/messages.po",
    "translations/de/LC_MESSAGES/messages.mo",
}


def public_source_path(name):
    path = PurePosixPath(name)
    if name in PUBLIC_FILES:
        return True
    if path.parts and path.parts[0] in PUBLIC_DIRECTORIES:
        return not any(part in PRIVATE_PARTS for part in path.parts)
    return name == "docs/api-inventory.md" or name.startswith(("docs/public/", "docs/adr/"))


def archive_entries(stream):
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise ValueError("Archive symlinks are forbidden")
                if info.file_size > 16 * 1024 * 1024:
                    raise ValueError("Oversized archive entry")
                yield info.filename, archive.read(info)
    else:
        if hasattr(stream, "seek"):
            stream.seek(0)
            archive = tarfile.open(fileobj=stream)
        else:
            archive = tarfile.open(stream)
        with archive:
            for info in archive:
                if info.isdir():
                    continue
                if not info.isfile() or info.size > 16 * 1024 * 1024:
                    raise ValueError(
                        "Archive links, special files and oversized entries are forbidden"
                    )
                handle = archive.extractfile(info)
                if handle is None:
                    raise ValueError("Unreadable archive entry")
                yield info.name, handle.read()


def check_entry(name, data, depth=0):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Unsafe archive path")
    if (
        path.name in PRIVATE_NAMES
        or any(part in PRIVATE_PARTS for part in path.parts)
        or path.suffix == ".log"
    ):
        raise ValueError("Private development file in archive")
    if "/docs/prp/" in "/" + name or "/docs/publishing/" in "/" + name:
        raise ValueError("Private planning file in archive")
    if PRIVATE_MARKER in data or re.search(rb"/(?:home|mnt)/[A-Za-z0-9_/.-]+", data):
        raise ValueError("Private development content in archive")
    if re.search(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", data):
        raise ValueError("Private key material in archive")
    if re.search(
        rb"(?<![0-9])(?:10\.[0-9]+|192\.168|172\.(?:1[6-9]|2[0-9]|3[01]))\.[0-9]+\.[0-9]+", data
    ):
        raise ValueError("Private network address in archive")
    if re.search(rb"https?://[A-Za-z0-9.-]+\.(?:internal|local|lan)(?:[/:\s]|$)", data):
        raise ValueError("Private service address in archive")
    if zipfile.is_zipfile(io.BytesIO(data)) or name.endswith((".tar.gz", ".tgz")):
        if depth >= 3:
            raise ValueError("Excessive nested archive depth")
        for nested_name, nested_data in archive_entries(io.BytesIO(data)):
            check_entry(nested_name, nested_data, depth + 1)


def unique_entries(path):
    entries = {}
    total_size = 0
    for name, data in archive_entries(path):
        if name in entries:
            raise ValueError("Duplicate archive entry")
        total_size += len(data)
        if len(entries) >= 10000 or total_size > 128 * 1024 * 1024:
            raise ValueError("Excessive archive size")
        entries[name] = data
    return entries


def check_archive(path):
    entries = unique_entries(path)
    for name, data in entries.items():
        check_entry(name, data)
    if not entries:
        raise ValueError("Empty archive")
    return len(entries)


def check_package(path):
    entries = unique_entries(path)
    package = "octoprint_mqttforusbrelaycontrol/"
    names = {name.split(package, 1)[1] for name in entries if package in name}
    if REQUIRED_ASSETS - names:
        raise ValueError("Required package assets are missing")
    if str(path).endswith(".whl"):
        entry_points = [
            data for name, data in entries.items() if name.endswith(".dist-info/entry_points.txt")
        ]
        if (
            len(entry_points) != 1
            or b"mqttforusbrelaycontrol = octoprint_mqttforusbrelaycontrol" not in entry_points[0]
            or b"[octoprint.plugin]" not in entry_points[0]
        ):
            raise ValueError("The OctoPrint entry point is missing or inconsistent")
    elif not any(name.endswith("pyproject.toml") for name in entries):
        raise ValueError("Source archive is missing pyproject.toml")
    return check_archive(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    arguments = parser.parse_args()
    for path in arguments.archives:
        count = check_package(path)
        print(f"Checked {path.name}: {count} entries")


if __name__ == "__main__":
    main()
