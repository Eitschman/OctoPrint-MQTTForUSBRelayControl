# Release readiness and beta procedure

The owner confirms human review and successful installation and testing on real
hardware. Detailed H01–H09 results and an independent audit are not claimed. The
repository is public; GitHub private vulnerability reporting is enabled. License
AGPL-3.0-or-later and maintainer Eitschman are approved.
[Beta 0.1.0b1](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases/tag/0.1.0b1) was published on 2026-11-27 from approved commit
`92953db96a0888a95de20fdadf6f17ddf6a24929`. The owner subsequently approved completion
of the beta and publication of [stable 0.1.0](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases/tag/0.1.0).
Official registration remains pending.

The owner confirms that installation from the public beta URL works perfectly.
This is owner feedback, not an external compatibility survey.
Stable `0.1.0` is documented in the [release notes](release-notes-0.1.0.md).
Later releases require their own verification and approval.

The historical beta is `0.1.0b1`; new installations should use stable `0.1.0`. The [beta guide](beta-guide.md) and
[release notes](release-notes-0.1.0b1.md) describe its archive and limitations.
Run `uv run python tools/check_release_readiness.py --stage beta --evidence <local-evidence.json>`
against the actual local approval record. Publication requires explicit approval.
The default `--stage stable` additionally requires completion of the beta. A first
beta cannot require its own completion before publication. Both stages retain human,
hardware, advisory and publication checks; neither accepts a development snapshot.
The command checks recorded booleans and metadata; it does not manufacture evidence.

Before release, verify the approved license and identities, review all internal API hooks,
resolve or explicitly assess dependency advisories, run the complete portable suite,
record the actual scope of human/hardware evidence and inspect clean actual screenshots.
Rebuild and inspect wheel, sdist and curated ZIP after final changes. Record SHA-256,
version, source provenance, dependency inventory, checks and remaining limitations.
The current CI contains no public release job. Security reports are retained as
GitHub Actions artifacts for 14 days. The official registry checks and site build
run in the quality workflow. The separate security workflow checks runtime code,
authorization and dependency additions against an identical official host on pushes,
pull requests, weekly and on demand. All inherited findings remain reported; see
the [security review](security-review.md) for the exact scope and coverage limits.
Passing checks are not an official acceptance or host-security guarantee.
See [registry preparation](registry.md) for the listing and remaining URL/date checks.

## Beta feedback

The first public beta and its prerelease source are approved. Later releases require
their own approval and verification. Install
only on a recoverable isolated instance, record Python/OctoPrint/USB/MQTT/HA versions,
active mode and channel, and compare requested state, readback and the physical output.
Exercise startup, both directions, retained replay, broker outage/reconnect, HA birth,
configuration reconstruction and uninstall. Stop immediately on an unintended output.
Never include credentials, complete server configurations or unredacted logs in feedback.
Use the compatibility and bug issue templates in the public repository.

Seven synthetic-environment screenshots and the approved featured image are included
in the [gallery](screenshots.md). They show English light/dark settings, German,
compact layout, diagnostics and actual Home Assistant test device/entity pages.
The gallery records their capture dates and scope. They do not demonstrate every
entity type or physical output. The owner confirms real-hardware installation/testing;
detailed H01–H09 records are not claimed or substituted with synthetic results.

## Updates and retirement

Keep the single version source and changelog synchronized. Development, alpha, beta,
RC and stable versions follow PEP 440 ordering; stable selection excludes prereleases.
The update hook is configured for the approved public Eitschman repository.
Its source factory accepts only the companion repository name and a validated owner,
and constructs the corresponding archive URL. It performs no network requests itself.
Installed OctoPrint release selection, stable/beta filtering and offline responses are tested.
Verify the real published tag and archive after publication.

For each later update repeat security, compatibility, migration, artifact and rollback
checks; preserve the original registry registration date. Document supported versions,
security response and deprecation dates. If maintenance ends, publish an approved
retirement notice and update the registry status rather than leaving support promises.
