"""Release approval cannot be inferred from successful software tests."""

from tools.check_release_readiness import release_blockers


def test_v03_v12_missing_approvals_block_release(tmp_path):
    assert "Owner-approved project license is missing" in release_blockers(tmp_path, {})
    (tmp_path / "LICENSE").write_text("Synthetic fixture only")
    evidence = dict.fromkeys(
        (
            "license_approved",
            "identity_approved",
            "human_review",
            "hardware_tests",
            "beta_completed",
            "advisories_reviewed",
            "publication_authorized",
        ),
        True,
    )
    evidence.update(
        version="0.1.0",
        homepage="https://example.org/",
        source="https://example.org/source",
        archive="https://example.org/archive.zip",
        maintainer="Synthetic fixture",
    )
    assert release_blockers(tmp_path, evidence) == []
    evidence["human_review"] = "true"
    assert release_blockers(tmp_path, evidence)


def test_first_beta_does_not_require_a_completed_beta_but_stable_does(tmp_path):
    (tmp_path / "LICENSE").write_text("Synthetic fixture only")
    evidence = dict.fromkeys(("license_approved", "identity_approved", "human_review",
                              "hardware_tests", "advisories_reviewed", "publication_authorized"), True)
    evidence.update(version="0.1.0b1", homepage="https://example.org/",
                    source="https://example.org/source", archive="https://example.org/archive.zip",
                    maintainer="Synthetic maintainer")
    assert release_blockers(tmp_path, evidence, "beta") == []
    assert "Release evidence is missing: beta_completed" in release_blockers(tmp_path, evidence)
    evidence["human_review"] = False
    assert "Release evidence is missing: human_review" in release_blockers(tmp_path, evidence, "beta")
    evidence["human_review"] = True
    evidence["publication_authorized"] = False
    assert "Release evidence is missing: publication_authorized" in release_blockers(tmp_path, evidence, "beta")


def test_release_stage_rejects_wrong_version_kind(tmp_path):
    evidence = {"version": "0.1.0.dev5"}
    assert "A development snapshot is not a public release" in release_blockers(tmp_path, evidence, "beta")
    evidence["version"] = "0.1.0"
    assert "A beta release must use a prerelease version" in release_blockers(tmp_path, evidence, "beta")
    evidence["version"] = "0.1.0b1"
    assert "A stable release must not use a prerelease version" in release_blockers(tmp_path, evidence)
