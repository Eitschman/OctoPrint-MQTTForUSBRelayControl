# Official OctoPrint registry preparation

The registration template is [extras/mqttforusbrelaycontrol.md](../../extras/mqttforusbrelaycontrol.md).
The owner approved AGPL-3.0-or-later and public maintainer Eitschman on 2026-11-27.
Python 3.11 is the minimum. Package, OctoPrint and registry metadata use the same
identifier, Python requirement, license and author. AI-assisted development is
disclosed with the mandatory `ai-developed` attribute.

## Checks performed before submission

The quality workflow uses the official registry revision
`95c543a6dda048df2a8edca7596e7549e0cb6fcb` from 2026-11-27. The validator and its
requirements are downloaded from that immutable revision and verified by SHA-256.
Neither file is patched. Their tools run in a separate Python 3.11 environment.

The actual project template is checked with the official PR flags:

```sh
uv run --no-project --python 3.11 python tools/validate_registry_fixtures.py --prepare-only
uv venv .registry --python 3.11
uv pip install --python .registry/bin/python -r artifacts/registry-validator/requirements.txt
.registry/bin/python tools/validate_registry_fixtures.py
.registry/bin/python tools/validate_registry_entry.py
```

The project validator also rejects metadata drift and checks local image existence,
which the inspected upstream validator does not reliably enforce. Negative fixtures
exercise missing fields and incorrect identifiers/images. They do not replace the
actual project template check.

The same workflow checks out the full official registry at the pinned revision,
adds our entry, validates its front matter, and runs its normal Ruby 3.4/Bundler
Jekyll build. Generated `plugins.json`, `notices.json`, `search.json`, the RSS feed
and our plugin page are checked. JSON output must contain exactly one project entry
with the approved metadata. No official source, Gemfile or dependency constraint
is modified. CI performs no Pages deployment, registry submission or public release.

## Host dependency findings

The separate OctoPrint dependency security workflow audits the entire resolved test
environment on pushes, pull requests, a weekly schedule and manual requests. It
remains strict: no ignored advisories, severity filters or `continue-on-error`.
Known OctoPrint dependency findings remain unresolved. Passing plugin quality or
registry checks does not certify that the host is free of vulnerabilities. The
owner must assess these findings before recommending a deployment or release.
See the [dependency review](dependency-review.md).

## Final publication checks

The template currently targets the planned `0.1.0` release archive. That tag and
public archive do not exist yet; schema validation does not verify URL availability.
Before submission, publish the separately approved release, verify the exact archive
URL without authentication, and set the actual first-registration date. Keep that
date unchanged on later registry updates. Prepare and review the real screenshot
bundle and update any image references before copying the entry to the official
repository's `_plugins` directory.

The source repository is still private. It must become publicly readable before
registration. The human maintainer must understand and maintain the code; passing
automation does not establish that review or guarantee acceptance by OctoPrint.
The remaining project release checks are in [release readiness](release-readiness.md).

Primary sources: [official registration policy](https://plugins.octoprint.org/help/registering/),
[official PR checks](https://github.com/OctoPrint/plugins.octoprint.org/blob/95c543a6dda048df2a8edca7596e7549e0cb6fcb/.github/workflows/validate-pull-requests.yml)
and [official site-build checks](https://github.com/OctoPrint/plugins.octoprint.org/blob/95c543a6dda048df2a8edca7596e7549e0cb6fcb/.github/workflows/publish-to-github-pages.yml).
