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
        version="0.1.0b1",
        homepage="https://example.org/",
        source="https://example.org/source",
        archive="https://example.org/archive.zip",
        maintainer="Synthetic fixture",
    )
    assert release_blockers(tmp_path, evidence) == []
    evidence["human_review"] = "true"
    assert release_blockers(tmp_path, evidence)
