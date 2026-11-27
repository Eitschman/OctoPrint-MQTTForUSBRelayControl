# MQTT for USB Relay Control 0.1.0b1

First beta. Check the [releases page](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases)
for published downloads.

Expose the relays configured in USB Relay Control as binary Home Assistant MQTT
switches, lights or fans through the existing OctoPrint-MQTT connection. Both
OctoPrint interfaces receive verified relay state updates. By default, entities join
the device supplied by the optional HomeAssistant Discovery plugin; the companion
provides overrides and a separate-device fallback.

The companion opens no USB devices or additional MQTT connection, does not poll,
and leaves foreign plugin files and settings unchanged. It rejects identifiable
retained commands, expires stale work, bounds the queue and spaces channel commands.
Discovery ownership and pending deletion records survive restarts. Reconnection reads
current state rather than replaying historical snapshots.

## Requirements and installation

Linux; Python 3.11+; official OctoPrint >=1.11.2; USB Relay Control 1.0.0;
OctoPrint-MQTT 0.8.19 or 0.8.20 with configured Last Will. The primary automated
functional matrix is OctoPrint 2.0.1 on Python 3.11/3.13. Version-specific evidence and
limits are in [compatibility](compatibility.md). The owner confirms human review and
successful installation and testing on real hardware; automated tests use synthetic HID.

After this prerelease is published, use the exact tag archive described in the
[beta guide](beta-guide.md). Integration starts disabled. Configure the original
plugins first, then enable and expose intended channels. English UI and documentation,
German UI and installation instructions are included.

GitHub release updates use normal OctoPrint Software Update checks. Beta installations
include prereleases; stable builds exclude them. License: AGPL-3.0-or-later.
Maintainer: Eitschman. The project was developed with AI assistance.

## Known limitations and security

Nine known inherited host advisories remain in Tornado/zeroconf. The companion's
code checks and dependency comparisons are separate; no additional known findings
were found against the identical official baseline. No host dependency is overridden.
Source-only foreign plugins are outside PyPI advisory coverage. See the
[security review](security-review.md) for the individual assessment and scope.

MQTT helper acceptance is not delivery confirmation. A live retained publication
may arrive with its retained flag cleared; configure senders with retain disabled.
Readback reflects the controller, not the load. Without polling, untouched hardware
faults may remain undetected. Identical VID/PID boards cannot be selected independently
by the original plugin. Switch/light/fan entities provide ON/OFF only.

Use the [support channel](../../SUPPORT.md) for beta feedback and
[private reporting](../../SECURITY.md) for vulnerabilities. This beta is not yet listed
in the official OctoPrint Plugin Repository and has no independent security certification.
