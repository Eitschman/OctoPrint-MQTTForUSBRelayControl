# Security review — 2026-11-27

The companion's security gate checks its runtime code, authorization and command
boundaries, and whether installing its wheel adds known dependency vulnerabilities
to the same official host. It does not certify OctoPrint, other plugins, the broker,
physical wiring or the load connected to a relay. This is a maintainer review with
automated checks, not an independent penetration test.

## Reproducible checks and coverage

[Plugin security checks](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/actions/workflows/dependency-audit.yml)
runs on pushes, pull requests, weekly and on demand:

- Bandit 1.9.4 runs every default check against every runtime Python file, at all
  severity/confidence levels. `--ignore-nosec` prevents inline suppression. Findings,
  scanner errors and missing file coverage fail the job.
- Real disposable-server tests reject anonymous users, non-admin users and requests
  without CSRF protection. Command tests cover retained input, expiry, bounded queues,
  channel pacing and stale generations. Fault tests verify that failing callbacks do
  not stop the worker or expose exception contents.
- Eight dependency comparisons cover Python 3.11/3.13, official OctoPrint 2.0.1/2.0.2
  and MQTT 0.8.19/0.8.20. Each creates a fresh environment, normally resolves and
  installs OctoPrint, USB Relay Control and MQTT, then audits the installed inventory.
  It installs the newly built companion wheel into that same environment, checks
  dependency consistency again and audits the resulting inventory. Every baseline
  package version and the interpreter must remain identical.
- PyPA pip-audit 2.10.1 checks every installed PyPI package at its exact version.
  `--no-deps` is used only on that complete pinned audit inventory; installations
  resolve dependencies normally. The legacy USB Relay setup requires build isolation
  disabled so it can import the installed OctoPrint build helper. Runtime dependencies
  are neither skipped nor overridden.
- USB Relay Control, MQTT and the unreleased companion are source-only projects absent
  from PyPI's advisory index. Their exact versions and upstream commit URLs are
  recorded explicitly. They are **outside that database's advisory coverage**; this
  is not a claim that they have no vulnerabilities. The companion is checked through
  code analysis and tests. No security audit of all foreign plugin code is claimed.
- Missing, failed, skipped, inconsistent or incomplete indexed-package reports fail
  the comparison. CVE/GHSA/PYSEC aliases are grouped transitively per package/version.
  Any finding present only after installing the companion fails the job. Every
  inherited finding remains in the job summary and downloadable JSON reports.

A passing comparison means **no additional known dependency findings**. New host
advisories remain visible without making the companion's comparison fail. A new
companion dependency advisory does fail it. There is no CVE ignore list, severity
filter, dependency override or `continue-on-error`.

The quality workflow also runs the complete backend/browser/Home Assistant suites,
Node dependency audit, artifact privacy checks and unmodified official registry
checks. Passing registry checks do not imply a security endorsement.

```sh
uv run python tools/check_security_scan.py --output artifacts/security/local-bandit.json
uv run python tools/security_audit.py --python 3.11 --octoprint 2.0.2 --mqtt 0.8.20 --output artifacts/security/local-comparison
```

Use new output paths for each run. Reports contain package names, versions, known
advisory identifiers and public source provenance, without local authentication data.
CI retains these reports for 14 days. Network/database failures fail the job; rerun
only after resolving the failure. Audit-tool environments are separate from the host
and their dependencies are not part of the product inventory.

## Runtime review and hardening

The review covered settings/API authorization, MQTT input and topic validation,
worker lifetime and invalidation, instance wrappers, persistence, UI rendering and
artifact selection. No exploitable companion vulnerability was identified in this
review. Automated scans cannot establish absence of unknown vulnerabilities.

Internal runtime invariants now use explicit checks instead of assertions removed
by Python optimization. Failed diagnostic/notification callbacks emit exception-type
warnings and cannot silently terminate the command worker. Error contents and raw
MQTT payloads are not included in these fallback logs.

The companion uses admin-only protected Simple API commands and OctoPrint's CSRF
handling. Settings accept bounded, typed fields; concrete MQTT topics reject wildcards
and empty segments. Commands accept only ON/OFF, require an explicitly false retained
flag, and recheck age/generation before hardware work. UI values use text/value
bindings and template autoescaping. Persistent files have fixed companion-owned
paths and atomic replacement; the discovery ledger validates instance ownership
before deleting topics. Existing archive tests inspect privacy and contamination.

MQTT publishers authorized for a command topic can switch that relay. Broker
permissions/TLS belong to OctoPrint-MQTT and the deployment. A live retained publish
can arrive with the retained flag cleared by the broker; the helper API cannot
identify its history. Keep sender retain disabled and remove retained commands
before enabling a channel. Controller readback does not verify the connected load.

## Inherited findings: individual assessment

Regular installations currently report 14 entries representing **nine distinct
advisories** in Tornado 6.5.10 and zeroconf 0.148.0. The same findings exist before
installing the companion. These are open host risks, not accepted companion waivers.
The conditions below are source/advisory-based assessments; no attack traffic was
sent to a production instance and no exploitability test or deployment mitigation
was performed.

| Advisory | Reported fix | Assessment and remaining condition |
| --- | --- | --- |
| [CVE-2026-116577](https://github.com/tornadoweb/tornado/security/advisories/GHSA-pcg2-g6cj-q92c) | Tornado 6.6 | Folded HTTP headers can consume CPU before authentication. OctoPrint uses a Tornado HTTP server, so treat this as a potentially reachable host availability risk. Proxy/header limits need deployment-specific verification. |
| [CVE-2026-115927](https://github.com/tornadoweb/tornado/security/advisories/GHSA-r4j5-9xpp-3985) | Tornado 6.6 | Many tiny HTTP chunks can block the event loop. OctoPrint has custom streaming upload handlers and request-size limits; those do not establish immunity. Treat the host as potentially affected pending upstream assessment. |
| [CVE-2026-116578](https://github.com/tornadoweb/tornado/security/advisories/GHSA-pw9p-v7r6-gx4p) | Tornado 6.6 | Open redirects depend on handler/template behavior; the advisory also discusses StaticFileHandler hardening. The companion creates no Tornado redirect handler. Host/third-party route reachability remains unproven, not cleared. |
| [CVE-2026-126347](https://github.com/tornadoweb/tornado/security/advisories/GHSA-5cjw-f85j-cv6r) | Tornado 6.6.1 | Follow-up redirect parsing fix. The companion adds no affected handler. Retain the host finding because absence of a vulnerable route across all plugins is not established. |
| [CVE-2026-47180](https://github.com/python-zeroconf/python-zeroconf/security/advisories/GHSA-9pgc-3ccv-5297) | zeroconf 0.149.5 | Deep mDNS compression pointers can cause recursion/log/CPU exhaustion. OctoPrint's bundled Discovery plugin initializes zeroconf; an untrusted peer on a reachable mDNS link is the relevant condition. |
| [CVE-2026-47183](https://github.com/python-zeroconf/python-zeroconf/security/advisories/GHSA-phvx-9mgw-67r5) | zeroconf 0.149.6 | Malformed mDNS traffic can grow exception-deduplication memory. Potential host availability risk when its zeroconf listener is active and an untrusted adjacent sender can reach it. |
| [CVE-2026-47184](https://github.com/python-zeroconf/python-zeroconf/security/advisories/GHSA-rfg2-pjw2-56x2) | zeroconf 0.149.7 in the advisory database | An unbounded DNS record cache permits memory exhaustion. The advisory prose mentions 0.149.6 while database metadata reports 0.149.7; retain the conservative database fix and the unresolved host finding. |
| [CVE-2026-48045](https://github.com/python-zeroconf/python-zeroconf/security/advisories/GHSA-9663-mqmp-p9mm) | zeroconf 0.149.12 | Truncated mDNS queries can grow deferred queues/timers and consume CPU. Relevant to an active host listener reachable by an untrusted local-link peer. |
| [CVE-2026-48487](https://github.com/python-zeroconf/python-zeroconf/security/advisories/GHSA-qc2x-6f54-m6h9) | zeroconf 0.149.16 | Truncated records can enter the cache after missing length checks. This concerns integrity of discovered records; it is not evidence of code execution. Host discovery exposure needs deployment assessment. |

[OctoPrint 2.0.2's dependency contract](https://github.com/OctoPrint/OctoPrint/blob/2.0.2/pyproject.toml)
keeps Tornado below 6.6 and pins zeroconf 0.148, as does 2.0.1. The reported fixed
versions cannot be installed while satisfying those contracts. The companion must
not override them. The [host's HTTP server](https://github.com/OctoPrint/OctoPrint/blob/2.0.2/src/octoprint/server/__init__.py)
and [bundled Discovery implementation](https://github.com/OctoPrint/OctoPrint/blob/2.0.2/src/octoprint/plugins/discovery/__init__.py)
support the reachability assessments above; this does not establish exploitation in
any particular installation. Upstream fixes, host upgrades and human release review
remain necessary. No production settings were changed.
