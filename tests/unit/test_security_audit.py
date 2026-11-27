"""Security gates must reject additions, missing coverage and scanner failures."""

import copy

import pytest

from tools.security_audit import PROJECT, compare, parse_audit


def advisory(identifier="CVE-test-1", aliases=None):
    return {"id": identifier, "aliases": aliases or [], "fix_versions": ["2.0"]}


def report(vulnerabilities=None):
    return {"dependencies": [{"name": "host-library", "version": "1.0", "vulns": vulnerabilities or []}], "fixes": []}


EXPECTED = {"host-library": "1.0"}
BASELINE = {"python": "3.11.15", "packages": EXPECTED}
COMPANION = {"python": "3.11.15", "packages": {**EXPECTED, PROJECT: "0.1.0.dev5"}}


def test_identical_inherited_findings_are_reported_without_failing_the_comparison():
    findings = parse_audit(report([advisory()]), EXPECTED, 1)
    groups = compare(BASELINE, COMPANION, findings, findings)
    assert len(groups) == 1
    assert groups[0]["sources"] == ["baseline", "companion"]
    assert groups[0]["ids"] == ["CVE-test-1"]


def test_added_vulnerability_is_distinguished_from_inherited_findings():
    baseline = parse_audit(report([advisory()]), EXPECTED, 1)
    companion = parse_audit(report([advisory(), advisory("CVE-test-2")]), EXPECTED, 1)
    groups = compare(BASELINE, COMPANION, baseline, companion)
    assert [row["ids"] for row in groups if row["sources"] == ["companion"]] == [["CVE-test-2"]]


def test_findings_in_new_dependencies_are_not_treated_as_baseline_findings():
    companion = copy.deepcopy(COMPANION)
    companion["packages"]["new-library"] = "1.0"
    findings = [{"name": "new-library", "version": "1.0", "ids": ["CVE-new"], "fix_versions": []}]
    assert compare(BASELINE, companion, [], findings)[0]["sources"] == ["companion"]


def test_aliases_are_grouped_transitively_without_inflating_the_finding_count():
    baseline = parse_audit(report([advisory("GHSA-test"), advisory("PYSEC-test")]), EXPECTED, 1)
    companion = parse_audit(report([advisory("CVE-test", ["GHSA-test", "PYSEC-test"])]), EXPECTED, 1)
    groups = compare(BASELINE, COMPANION, baseline, companion)
    assert len(groups) == 1
    assert groups[0]["ids"] == ["CVE-test", "GHSA-test", "PYSEC-test"]
    assert groups[0]["sources"] == ["baseline", "companion"]


@pytest.mark.parametrize("change", ["host-version", "python", "missing-project", "missing-host", "contaminated-baseline"])
def test_different_or_contaminated_baselines_cannot_pass(change):
    baseline, companion = copy.deepcopy(BASELINE), copy.deepcopy(COMPANION)
    if change == "host-version":
        companion["packages"]["host-library"] = "2.0"
    elif change == "python":
        companion["python"] = "3.13.12"
    elif change == "missing-project":
        companion["packages"].pop(PROJECT)
    elif change == "missing-host":
        companion["packages"].pop("host-library")
    else:
        baseline["packages"][PROJECT] = "0.1.0.dev5"
    with pytest.raises(ValueError):
        compare(baseline, companion, [], [])


@pytest.mark.parametrize("data,exitcode", [
    ({}, 0), ([], 0), ({"dependencies": [], "fixes": []}, 0),
    ({"dependencies": [{"name": "host-library", "skip_reason": "Unavailable"}], "fixes": []}, 0),
    ({"dependencies": [{"name": "host-library", "version": "1.0"}], "fixes": []}, 0),
    (report(), 2), (report(), 1), (report([advisory()]), 0),
    (report([{"id": "CVE-test"}]), 1),
    ({"dependencies": report()["dependencies"] * 2, "fixes": []}, 0),
    ({"dependencies": [{"name": "host-library", "version": "2.0", "vulns": []}], "fixes": []}, 0),
])
def test_failed_incomplete_skipped_or_inconsistent_scans_fail_closed(data, exitcode):
    with pytest.raises(ValueError):
        parse_audit(data, EXPECTED, exitcode)


def test_complete_clean_reports_pass():
    assert parse_audit(report(), EXPECTED, 0) == []
    assert compare(BASELINE, COMPANION, [], []) == []
