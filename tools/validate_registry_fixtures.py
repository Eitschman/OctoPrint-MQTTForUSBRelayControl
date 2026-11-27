"""Exercise the official registry validator with synthetic metadata only."""

import argparse
import copy
import datetime
import hashlib
import json
import runpy
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(validator):
    contract = json.loads((ROOT / "tests/fixtures/registry-validator.json").read_text())
    if hashlib.sha256(validator.read_bytes()).hexdigest() != contract["sha256"]:
        raise ValueError("The official validator checksum changed; review before updating")
    module = runpy.run_path(str(validator))
    import frontmatter

    with tempfile.TemporaryDirectory(prefix="registry-fixtures-") as temporary:
        root = Path(temporary)
        directory = root / "_plugins"
        directory.mkdir()
        path = directory / "synthetic.md"
        image = root / "assets/img/plugins/synthetic/settings.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"synthetic validator path fixture; not a product screenshot")
        data = dict(
            layout="plugin",
            id="synthetic",
            title="Synthetic validator fixture",
            description="Not a real plugin listing",
            author="Synthetic test author",
            license="MIT",
            date=datetime.date(2026, 1, 1),
            homepage="https://example.org/",
            source="https://example.org/source",
            archive="https://example.org/archive.zip",
            attributes=["ai-developed"],
            compatibility={"python": ">=3.11", "octoprint": [">=1.11.2"]},
            screenshots=[
                {"url": "/assets/img/plugins/synthetic/settings.png", "alt": "Synthetic fixture"}
            ],
            featuredimage="/assets/img/plugins/synthetic/settings.png",
        )

        def validate(value):
            path.write_text(
                frontmatter.dumps(frontmatter.Post("Fixture only", **value)), encoding="utf-8"
            )
            return module["validate"](
                str(root),
                str(path),
                id_match=True,
                asset_match=True,
                internal_assets=True,
                screenshots_present=True,
                py3_compat_check=True,
            )

        assert validate(data) == []
        for key in ("title", "author", "compatibility"):
            invalid = copy.deepcopy(data)
            del invalid[key]
            try:
                validate(invalid)
            except Exception:
                pass
            else:
                raise AssertionError("The official validator accepted a defective fixture")
        invalid = copy.deepcopy(data)
        invalid["id"] = "wrong-id"
        assert validate(invalid), "An identifier mismatch must be reported"
        invalid = copy.deepcopy(data)
        invalid["featuredimage"] = "/assets/img/plugins/foreign/settings.png"
        try:
            validate(invalid)
        except Exception:
            pass
        else:
            raise AssertionError("A mismatched image folder was accepted")
        # Missing files require an independent filesystem check: the inspected validator
        # constructs Url(url) instead of invoking Url()(url) in its path-check branch.
        image.unlink()
        assert not (root / data["featuredimage"].lstrip("/")).is_file()
    print(
        "Official validator: valid fixture, three missing-field cases, ID and image mismatch checked"
    )
    print(
        "Missing image files require the additional local existence gate; no project listing is approved"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Explicitly download the checksummed public validator",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Download verified validator and requirements without running them",
    )
    parser.add_argument(
        "--validator",
        type=Path,
        default=ROOT / "artifacts/registry-validator/validate_front_matter.py",
    )
    arguments = parser.parse_args()
    if arguments.prepare or arguments.prepare_only:
        contract = json.loads((ROOT / "tests/fixtures/registry-validator.json").read_text())
        arguments.validator.parent.mkdir(parents=True, exist_ok=True)
        downloads = (
            (contract, arguments.validator),
            (contract["requirements"], arguments.validator.parent / "requirements.txt"),
        )
        for entry, destination in downloads:
            with urllib.request.urlopen(entry["url"], timeout=30) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("The official registry tool checksum changed")
            destination.write_bytes(data)
    if arguments.prepare_only:
        print("Prepared checksummed official registry validator and requirements")
        return
    run(arguments.validator)


if __name__ == "__main__":
    main()
