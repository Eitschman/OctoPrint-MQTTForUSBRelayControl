# Installation and configuration

This guide applies to beta `0.1.0b1`; check the [beta guide](beta-guide.md) for
release availability. The owner confirms human review
and successful installation and testing on real hardware. The owner has approved AGPL-3.0-or-later and maintainer Eitschman.
Detailed H01–H09 results are not claimed. Only install an archive listed on the releases page.
Do not install it on a production printer as part of the automated tests.

## Prerequisites

Use Python 3.11 or later and a supported OctoPrint installation. Install USB Relay
Control 1.0.0 and OctoPrint-MQTT 0.8.19 or 0.8.20 first. Configure the original relay
channels and verify their normal OctoPrint controls yourself. The companion reuses
those objects; it supplies no USB driver or broker credentials.

Configure the existing MQTT connection and enable its Last Will. The companion
never enables this setting for you. With Last Will disabled, commands and new
discovery are blocked and a prerequisite error appears. Retained Last Will is useful
for bootstrapping when connection happened before binding. Authorize access to MQTT
command topics at the broker; a fresh authorized message can operate hardware.

## Local package

Once the local build has passed its content checks, install its wheel using the
OctoPrint environment's Python and restart OctoPrint. A wheel from this working tree
is a licensed development artifact; an approved public release is still pending. Never install the project's
private working directory or a ZIP containing local configuration.

```sh
python -m pip install /path/to/approved-local-build.whl
```

See the [beta guide](beta-guide.md) for the planned tag archive and installation
steps. The repository is public; the beta archive becomes available after publication.

## Settings

Open Settings → MQTT for USB Relay Control. Integration starts disabled. Enable it,
then expose each desired channel. Choose Switch, Light or Fan and optionally a Home
Assistant name. All three domains provide binary On/Off only. Save through OctoPrint's
normal Save button; Close discards edits. Actions use the currently saved settings.

The channel list is read from USB Relay Control and cannot edit its hardware values.
Active Low inverts physical bit interpretation; logical ON always means the configured
active state. Channels 1–8 are supported independently; channel 0 is an upstream all-
channel operation, not a discoverable entity. Duplicate channels are blocked.

The MQTT prefix defaults to the existing plugin's base topic. Discovery defaults to
`homeassistant`; birth defaults to `homeassistant/status` with payload `online`.
Advanced settings expose these values, device grouping/name and local debug logging.
By default, relays join the existing device from the active **HomeAssistant Discovery**
plugin, using its exact `node_id`. An empty device name follows that plugin's name.
This optional integration reads only `node_id` and `node_name`; it does not change
the other plugin or contact Home Assistant directly.

If that plugin is missing or disabled, relays use the companion's separate device.
During a transient lookup/read failure or invalid source value, the last validated
assignment is kept, including after restart. Only that identity/name are stored
in the companion data folder's `device-identity.json`; no foreign settings are
written. Diagnostics show a cached assignment or unavailable source. With no prior
assignment, the separate device is used. A readable new identifier replaces the old
assignment. To keep a separate device explicitly, uncheck **Use existing
OctoPrint device when available** and leave **Device identifier override** empty.
Its empty device name follows the OctoPrint-MQTT base topic without trailing slashes
(`octoPrint/` becomes `octoPrint`), independently of a custom companion MQTT prefix.

A nonempty **Device identifier override** takes precedence over automatic grouping
and the checkbox. Enter the exact MQTT device identifier, including letter case,
not its display name. Leave the name empty to preserve a custom target's existing
name. A custom name can rename the shared device; another discovery publisher can
subsequently overwrite that name. Manufacturer/model metadata are not copied.

After upgrading from dev2, save the settings or use **Submit discovery** to submit
the updated assignment. Entity unique IDs and discovery/command/state topics stay
unchanged. Device-based automations referencing the former separate device need
review when moving its entities. Do not delete the existing OctoPrint device or its
other entities. Older Home Assistant versions may leave an empty former device.
Use concrete topics without wildcards, NULs or empty segments. Commands, states,
availability, discovery, birth and Last Will must not collide.

**Command protection** in advanced settings defaults to a **5-second maximum
command age** (range 1–60) and a **0.25-second minimum channel interval** (range
0.1–10). The interval starts after a command finishes. Commands wait for their
channel and expire before execution if too old; other channels and state updates
can proceed. These controls affect companion MQTT commands. They cannot cancel a
running hardware call. Original relay buttons retain their behavior. Use Save to
apply changes. Diagnostics show queued/expired/overflow counts and sampled operation
durations. A call exceeding 2 seconds triggers a warning; no hardware polling is used.
Controller readback confirms only reported controller bits, not electrical power
at the connected load. Investigate slow/blocked operations before restarting; a
restart-required warning prevents unsafe companion rebinding after failed teardown.

Home Assistant discovers entities from retained configurations. Each entity requires
both the existing OctoPrint-MQTT Last Will status and its own channel availability.
A missing readback makes the channel unavailable. MQTT delivery cannot be guaranteed.

Read current states performs a read-only reconciliation. Submit discovery republishes
the current discovery intent. Submit pending deletions displays a confirmation with
its count and retries only owned obsolete discovery topics. Neither action switches
hardware or calls the original settings-save handler.

## Cloned OctoPrint instances

Shared grouping also depends on the other discovery plugin's identity. The
companion's offline clone action does not change that plugin's copied `node_id` or
a manual device identifier override; configure those independently for a clone.

A filesystem clone copies the UUID and cannot be detected automatically. Keep the
clone disconnected from MQTT. Establish a known offline connection status, then use
New identity for offline clone and explicitly confirm. The new UUID is persisted;
the copied old ledger is detached locally. No old identity topic is published or
deleted. Configure the clone's broker/prefix as appropriate before reconnecting.
Two connected copies sharing a UUID can conflict; do not connect a clone first.
Channel selections belong to the old identity and are not automatically enabled for
the clone. Review and enable its newly identified channels explicitly.

## Removal

Disable integration while the existing broker is available and submit pending
owned discovery deletions. Verify removal in Home Assistant and at the broker;
helper acceptance does not prove delivery. Uninstall the companion and restart
OctoPrint. Original hardware configuration remains in USB Relay Control. Removal
while offline can leave retained discovery; delete only the recorded owned topics
manually later. No companion action powers down a relay automatically.

See [topics](mqtt-topics.md), [compatibility](compatibility.md),
[troubleshooting](troubleshooting.md) and [privacy](privacy.md).
