# Dependency review — 2026-11-26

The companion's only declared runtime dependency is OctoPrint. USB Relay Control and
OctoPrint-MQTT must already be installed. No upstream implementation is bundled.
The exact resolved test environments were audited with public `pip-audit 2.10.1`;
the locked Node suite was checked with `pnpm audit`. These checks report advisories,
not exploitability determinations or a guarantee that all vulnerabilities are known.

| Audited environment | Actual result |
| --- | --- |
| Python 3.9.25 / OctoPrint 2.0.1 baseline | 121 reported entries across 9 packages, including duplicate advisory IDs |
| Python 3.13.12 / OctoPrint 2.0.1, updated pytest/pip | 14 reported entries across Tornado 6.5.10 and zeroconf 0.148.0, including duplicates |
| Locked Node test dependencies | No reported advisories |

The Python 3.9 report also names Pillow, pip, pytest, requests, setuptools, soupsieve
and urllib3. Several fixed releases require a newer interpreter. OctoPrint 2.0.1 pins
zeroconf to 0.148 and restricts Tornado below 6.6, while reported fixes require newer
versions. Its Python-3.9 branch also pins requests 2.32.5. The companion must not silently
override the host application's dependency contract. Python 3.9 remains the required
functional compatibility target; that is not a security endorsement of this baseline.

The development group now selects pytest 9.2.0 and pip 26.3 on Python 3.10+, preserving
compatible legacy tooling on 3.9. The unnecessary setuptools build upper bound was
removed. These changes do not resolve the host's Tornado/zeroconf restrictions.
No advisory was silently waived. A production recommendation and public release require
human assessment of the current host version, reachable features, upstream fixes and
supported interpreter. The strict advisory CI gate may fail until that is resolved.

Reproduce the audit against the actual isolated environment, not just top-level names:

```sh
uvx --python 3.13 pip-audit==2.10.1 --path .venv/lib/python3.13/site-packages --skip-editable -f json -o artifacts/advisories.json
pnpm audit --json
```

Use the interpreter's actual site-packages path when it differs. Keep raw environment
reports local and inspect them before sharing. Resolved Python and Node license metadata
was inventoried separately; upstream metadata is not a legal compatibility approval.
The exact AGPL recommendation and unresolved owner approval are in
[third-party notices](../../THIRD_PARTY_NOTICES.md).
