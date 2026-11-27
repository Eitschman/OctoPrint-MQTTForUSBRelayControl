"""Prove privacy rejection for each actual archive format without altering originals."""

import argparse
import io
import tarfile
import tempfile
import zipfile
from pathlib import Path

from check_artifact import PRIVATE_MARKER, archive_entries, check_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    arguments = parser.parse_args()
    count = 0
    with tempfile.TemporaryDirectory(prefix="artifact-negative-fixtures-") as temporary:
        for source in arguments.archives:
            check_package(source)
            entries = list(archive_entries(source))
            for index, (name, content) in enumerate(
                (
                    ("start-codex.sh", b"synthetic local launcher"),
                    ("AGENTS.md", b"synthetic private instructions"),
                    ("docs/public/renamed.md", PRIVATE_MARKER),
                )
            ):
                path = Path(temporary) / (str(index) + "-" + source.name)
                modified = [*entries, ("nested/" + name, content)]
                if zipfile.is_zipfile(source):
                    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                        for entry, data in modified:
                            archive.writestr(entry, data)
                else:
                    with tarfile.open(path, "w:gz") as archive:
                        for entry, data in modified:
                            info = tarfile.TarInfo(entry)
                            info.size = len(data)
                            archive.addfile(info, io.BytesIO(data))
                try:
                    check_package(path)
                except ValueError as error:
                    assert "Private" in str(error), (
                        "The negative fixture failed for an unrelated reason"
                    )
                else:
                    raise AssertionError("A contaminated archive passed the privacy gate")
                count += 1
    print(f"Rejected {count} controlled archive contaminations; original archives were unchanged")


if __name__ == "__main__":
    main()
