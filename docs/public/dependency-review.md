# Dependency review — 2026-11-27

The companion declares only OctoPrint as a runtime dependency. USB Relay Control and
OctoPrint-MQTT must already be installed. No upstream implementation is bundled.
Python 3.11 is the minimum; the old Python 3.9 audit is historical evidence only.

The [security review](security-review.md) defines the current gates, reproducible
commands, database coverage limits and individual assessment of all nine inherited
advisories. Complete regular host installations are compared before and after adding
the companion wheel. Every baseline package must retain its version. Additional known
findings, incomplete reports or dependency conflicts fail the comparison. Host findings
remain visible in job summaries and JSON artifacts without being attributed to the
companion. Source-only foreign plugins are explicitly outside PyPI advisory coverage.

Current official OctoPrint 2.0.1/2.0.2 installations report 14 entries representing
nine distinct advisories in Tornado 6.5.10 and zeroconf 0.148.0, both before and after
installing the companion. The fixed versions conflict with OctoPrint's dependency
contract. No dependency override, CVE ignore list, severity filter or patched host is
used. The locked Node dependency audit reports no advisories.

[Plugin security checks](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/actions/workflows/dependency-audit.yml)
runs every push/PR, weekly and on demand. Green means the companion passed its code,
authorization and dependency-comparison checks; it does not mean the host is free of
known vulnerabilities. The separate quality workflow validates functional and official
registry compatibility. Neither workflow grants publication approval.

License metadata was inventoried separately; upstream metadata is not a legal
compatibility approval. The approved companion license and upstream boundaries are
in [third-party notices](../../THIRD_PARTY_NOTICES.md).
