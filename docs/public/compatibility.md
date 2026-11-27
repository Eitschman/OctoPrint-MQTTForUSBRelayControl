# Compatibility evidence

The dev3 optional **HomeAssistant Discovery** grouping contract reads `node_id` and
`node_name` from an enabled plugin with identifier `homeassistant`. Legacy six-character
and newer UUID-hex IDs are preserved exactly. Configuration/serialization regressions
and Home Assistant 2026.11.3 schemas are tested. Actual isolated HA runtime tests now
verify moving an existing entity to the shared printer device and back, preserving
its unique ID and the printer's metadata and unrelated entity.

Python minimum: **3.11**, starting with dev5. Python 3.9 and 3.10 are no longer
supported. Earlier Python 3.9 results below are historical evidence for dev0–dev4,
not compatibility claims for dev5. Raising the minimum does not resolve the
[remaining OctoPrint dependency advisories](dependency-review.md).

Dev5 local checks passed on Python 3.11.15 with MQTT 0.8.20 and Python 3.13.12
with MQTT 0.8.19: 248 unit/contract tests on each interpreter, at least 91.17%
branch-inclusive coverage, and matching mypy targets. The updated CI runs both
MQTT versions on both interpreters. Service and archive checks are recorded in
the development report. A separate regular wheel installation on official
OctoPrint 2.0.2 passes dependency-consistency and installed-entry-point checks;
this does not establish a full 2.0.2 runtime contract.

The following table records the earlier dev0–dev4 integration evidence:

| OctoPrint | Python | USB Relay Control | MQTT | Evidence |
| --- | --- | --- | --- | --- |
| 2.0.1 | 3.9.25 | 1.0.0 | 0.8.20 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 2.0.1 | 3.9.25 | 1.0.0 | 0.8.19 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 2.0.1 | 3.13.12 | 1.0.0 | 0.8.20 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 2.0.1 | 3.13.12 | 1.0.0 | 0.8.19 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 1.11.2 | 3.9 | 1.0.0 | 0.8.20 | Tested minimum: installed plugins + real broker + synthetic HID passed |
| 2.0.2 | 3.11+ | 1.0.0 | 0.8.19/0.8.20 | Newer upstream version, not yet tested |

On 2026-11-27, dev4 passed actual Chromium journeys in English, German and a compact
viewport, plus a separate read-failure journey. Each project uses a fresh server and
broker. Eleven Home Assistant checks passed, including nine schemas, device migration
and the actual HA-to-companion-to-original roundtrip with synthetic hardware.
The OctoPrint 1.11.2 minimum result remains historical dev0/dev1 evidence.

The matrix establishes software integration, not actual USB timing or physical safety.
Other USB/MQTT versions are conservatively rejected until their contracts are verified.
Other OctoPrint versions may be compatible but are not claimed tested. The automated
matrix above uses Linux and synthetic HID.

The project owner reports successful use of the development builds on real hardware.
This is practical hardware evidence. The hardware model, complete software versions
and individual H01–H09 results have not yet been recorded, so no additional platform
or device compatibility matrix is claimed. See the [manual test plan](manual-test-plan.md)
for the remaining formal checks and the development report for schema and browser evidence.
