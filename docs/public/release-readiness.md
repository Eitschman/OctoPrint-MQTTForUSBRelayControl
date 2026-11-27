# Release readiness and beta procedure

The project owner reports successful use of this development build on real hardware.
A complete H01–H09 result record is still pending. The private source repository is
available to its collaborators; public distribution has not been approved.
Successful tests do not grant a license, establish authorship or authorize publication.
Run `uv run python tools/check_release_readiness.py`; its current nonzero result is
intentional. The local approval-evidence JSON must use explicit booleans for license,
identity, human review, hardware tests, beta completion, advisory review and publication
authorization. It must identify the version, maintainer and actual homepage/source/archive.
The command checks recorded prerequisites; a human must verify their evidence and links.

Before release, approve the exact license and identities, review all internal API hooks,
resolve or explicitly assess dependency advisories, run the complete portable suite,
perform the separately authorized hardware plan and inspect clean actual screenshots.
Rebuild and inspect wheel, sdist and curated ZIP after final changes. Record SHA-256,
version, source provenance, dependency inventory, checks and remaining limitations.
The current CI contains no public upload or release job.

## Beta feedback

A public beta requires separate permission and an approved prerelease source. Install
only on a recoverable isolated instance, record Python/OctoPrint/USB/MQTT/HA versions,
active mode and channel, and compare requested state, readback and the physical output.
Exercise startup, both directions, retained replay, broker outage/reconnect, HA birth,
configuration reconstruction and uninstall. Stop immediately on an unintended output.
Never include credentials, complete server configurations or unredacted logs in feedback.
Use the compatibility and bug issue templates once an actual approved repository exists.

Required screenshot subjects are: the overall settings page; recognized relay identity;
switch/light/fan selection; MQTT, frontend compatibility and LWT diagnostics; the actual
HA device; the HA entities for all three domains; and state agreement after both HA and
original OctoPrint actions. Narrow-layout and explicit read-failure captures supplement
these subjects. Capture actual rendered UI with synthetic data, inspect every image
and provide descriptive English alt text. Local settings and actual HA device/entity
captures exist. The complete approved seven-image release set and formal H01–H09
result record remain separate release gates. The owner's successful hardware use is
recorded in the development report; synthetic HID tests provide software evidence.

## Updates and retirement

Keep the single version source and changelog synchronized. Development, alpha, beta,
RC and stable versions follow PEP 440 ordering; stable selection excludes prereleases.
The update hook is inactive until an approved source is compiled into `updates.py`.
Its source factory accepts only the companion repository name and a validated owner,
and constructs the corresponding archive URL. It performs no network requests itself.
Test installed OctoPrint release selection and offline responses before enabling it.

For each later update repeat security, compatibility, migration, artifact and rollback
checks; preserve the original registry registration date. Document supported versions,
security response and deprecation dates. If maintenance ends, publish an approved
retirement notice and update the registry status rather than leaving support promises.
