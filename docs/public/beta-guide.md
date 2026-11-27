# First beta: installation and feedback

This guide describes beta `0.1.0b1`. Check the [releases page](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases)
before installing: use the tag archive below only when that prerelease is listed.
Before publication the URL returns 404. Do not substitute an unreviewed branch
snapshot for a published beta.

## Prerequisites

Use Linux, Python 3.11 or later and a supported official OctoPrint installation.
The primary functional matrix covers OctoPrint 2.0.1 on Python 3.11/3.13, USB Relay
Control 1.0.0 and MQTT 0.8.19/0.8.20. Regular dependency installations additionally
cover OctoPrint 2.0.2; that is not a full 2.0.2 hardware/runtime compatibility claim.
Configure and test USB Relay Control and MQTT, including MQTT Last Will, first.

Back up the OctoPrint configuration. Use a recoverable test instance and a safe relay
load. The owner confirms successful real-hardware installation and testing; automated
verification uses synthetic hardware. Controller readback does not verify power at
the load. Read the [security review](security-review.md) before choosing a host.

## Install the approved prerelease

After publication, open OctoPrint Settings → Plugin Manager → Get More → from URL:

```text
https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/archive/refs/tags/0.1.0b1.zip
```

Install, restart OctoPrint and confirm version `0.1.0b1`. The same archive can be
installed with the Python that runs OctoPrint:

```sh
python -m pip install 'https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/archive/refs/tags/0.1.0b1.zip'
```

The companion requires no additional MQTT password or connection. Follow the
[English guide](installation.md) or [German guide](installation-de.md), enable the
integration and expose the intended channels. Verify both ON and OFF in OctoPrint
and Home Assistant. Check actual relay output independently if safe to do so.

## Updates and feedback

The beta's normal OctoPrint Software Update hook follows GitHub prereleases using
PEP 440 comparison. Stable plugin builds exclude prereleases. No periodic relay
polling is added. Check the displayed target before approving an update.

Test the relevant cases in the [manual test plan](manual-test-plan.md), particularly
startup, both control directions, retained replay, broker outage/reconnect, HA birth,
configuration changes and cleanup. Stop on an unexpected output. Record only cases
you actually ran, distinguishing observations from assumptions.

Report ordinary bugs through the [issue templates](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/issues/new/choose).
Include versions, hardware model/channel/active mode, steps, expected/actual behavior
and redacted diagnostics. Report vulnerabilities through [private reporting](../../SECURITY.md).
Do not attach credentials, full configurations or unreviewed logs/screenshots.

For rollback, first disable the integration and follow the cleanup and uninstall
instructions. Restore a previous reviewed package and configuration as appropriate.
Offline discovery cleanup may remain pending; never delete unrelated MQTT topics.
