# MQTT for USB Relay Control 0.1.0

First stable release, following owner-approved completion of the beta.
[Download 0.1.0](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases/tag/0.1.0).

Expose USB Relay Control channels as binary Home Assistant MQTT switches, lights or
fans through the existing OctoPrint-MQTT connection. The companion uses existing relay
objects and verified controller readback, without polling, direct USB access, a second
MQTT connection or foreign plugin changes. Default discovery joins the optional
HomeAssistant Discovery device; manual and separate-device overrides are available.

## Changes from the beta

No relay behavior changed since `0.1.0b1`. Version metadata and installation documents
are finalized for the stable release. The owner reports that installation from the
published beta URL works perfectly, following earlier successful real-hardware use.
Automated tests use synthetic hardware; no external hardware survey is claimed.

Stable installations exclude prereleases through OctoPrint's normal GitHub release
checker. The release-selection tests cover a beta advancing to stable and a stable
installation excluding a newer beta. Existing companion settings are preserved.

## Requirements and installation

Linux, Python 3.11+, official OctoPrint >=1.11.2, USB Relay Control 1.0.0 and
OctoPrint-MQTT 0.8.19/0.8.20 with Last Will enabled. Functional automation primarily
covers OctoPrint 2.0.1 on Python 3.11/3.13; regular dependency comparisons additionally
cover 2.0.2. Read the [compatibility matrix](compatibility.md).

Install this URL through
OctoPrint Settings → Plugin Manager → Get More → from URL, then restart OctoPrint:

```text
https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/archive/refs/tags/0.1.0.zip
```

The integration starts disabled on a new installation. Follow the
[English instructions](installation.md) or [German instructions](installation-de.md).
License: AGPL-3.0-or-later. Maintainer: Eitschman. Development is AI-assisted.

## Known limitations and security

Nine inherited host advisories in Tornado/zeroconf remain disclosed. No additional
known findings were found against the identical normally resolved official baseline;
no host dependencies are overridden. Source-only foreign plugins are outside PyPI
advisory coverage. See the [security review](security-review.md) for scope and risks.

MQTT acceptance is not delivery confirmation. Rejecting identifiable retained commands
cannot prevent every broker from clearing the retain flag on live publications; use
retain=false for commands. Controller readback is not proof of output at the load.
Without polling, untouched hardware faults may remain undetected. Identical VID/PID
boards cannot be independently selected by the original driver. All three entity types
provide ON/OFF control only. Offline discovery cleanup may remain pending.

Use [support](../../SUPPORT.md) for ordinary feedback and
[private reporting](../../SECURITY.md) for vulnerabilities. Official OctoPrint Plugin
Repository registration is pending; no security certification is claimed.
