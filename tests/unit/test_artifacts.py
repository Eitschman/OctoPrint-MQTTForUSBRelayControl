"""Negative privacy fixtures prove that renamed content also fails the gate."""

import zipfile

import pytest

from tools.check_artifact import PRIVATE_MARKER, check_archive, check_entry, public_source_path


@pytest.mark.parametrize(
    "path",
    [
        "start-codex.sh",
        "AGENTS.md",
        "docs/prp/PRP.md",
        "artifacts/config.yaml",
        ".env",
        "../escape",
        "/absolute",
    ],
)
def test_p02_v05_v07_v14_private_paths_are_rejected(path):
    with pytest.raises(ValueError):
        check_entry(path, b"ordinary text")


@pytest.mark.parametrize(
    "data",
    [
        PRIVATE_MARKER,
        b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
        b"/home/" + b"someone/private/config",
    ],
)
def test_v14_renamed_private_content_is_rejected(data):
    with pytest.raises(ValueError):
        check_entry("docs/public/innocent.md", data)


def test_positive_source_selection_and_real_archive(tmp_path):
    assert public_source_path("docs/public/architecture.md")
    assert not public_source_path("docs/prp/research.md")
    assert not public_source_path("start-codex.sh")
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("README.md", "Public documentation")
    assert check_archive(path) == 1


def test_nested_archive_cannot_hide_a_private_file(tmp_path):
    import io

    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("AGENTS.md", b"private")
    with pytest.raises(ValueError):
        check_entry("nested.zip", inner.getvalue())


def test_duplicate_entries_cannot_hide_an_earlier_private_payload(tmp_path):
    path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("README.md", PRIVATE_MARKER)
        with pytest.warns(UserWarning, match="Duplicate"):
            archive.writestr("README.md", b"public")
    with pytest.raises(ValueError, match="Duplicate"):
        check_archive(path)


@pytest.mark.parametrize(
    "data", [b"192." + b"168.10.20", b"http://" + b"printer.internal/", PRIVATE_MARKER]
)
def test_private_addresses_and_embedded_token_canaries(data):
    with pytest.raises(ValueError):
        check_entry("docs/public/renamed.md", data)


def test_missing_asset_or_entry_point_is_rejected(tmp_path):
    from tools.check_artifact import REQUIRED_ASSETS, check_package

    path = tmp_path / "broken.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for asset in REQUIRED_ASSETS:
            archive.writestr("octoprint_mqttforusbrelaycontrol/" + asset, b"fixture")
    with pytest.raises(ValueError, match="entry point"):
        check_package(path)
    with zipfile.ZipFile(tmp_path / "missing.zip", "w") as archive:
        archive.writestr("README.md", b"fixture")
    with pytest.raises(ValueError, match="assets"):
        check_package(tmp_path / "missing.zip")
