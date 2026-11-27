# Compatibility evidence

The dev3 optional **HomeAssistant Discovery** grouping contract reads `node_id` and
`node_name` from an enabled plugin with identifier `homeassistant`. Legacy six-character
and newer UUID-hex IDs are preserved exactly. Configuration/serialization regressions
and Home Assistant 2026.11.3 schemas are tested. A new actual end-to-end device-move
test is prepared but blocked by the current local socket restrictions; the earlier
server/browser matrix below does not establish that new dev3 runtime behavior.

Python minimum: **3.9**. OctoPrint 2.0 warns that Python 3.9 is past upstream Python
end of life; the user-selected minimum remains supported by this companion's local
software tests. Prefer a maintained Python interpreter for deployment.

| OctoPrint | Python | USB Relay Control | MQTT | Evidence |
| --- | --- | --- | --- | --- |
| 2.0.1 | 3.9.25 | 1.0.0 | 0.8.20 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 2.0.1 | 3.9.25 | 1.0.0 | 0.8.19 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 2.0.1 | 3.13.12 | 1.0.0 | 0.8.20 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 2.0.1 | 3.13.12 | 1.0.0 | 0.8.19 | Installed plugins + real loopback Mosquitto + synthetic HID passed |
| 1.11.2 | 3.9 | 1.0.0 | 0.8.20 | Tested minimum: installed plugins + real broker + synthetic HID passed |
| 2.0.2 | 3.9+ | 1.0.0 | 0.8.19/0.8.20 | Newer upstream version, not yet tested |

The matrix establishes software integration, not actual USB timing or physical safety.
Other USB/MQTT versions are conservatively rejected until their contracts are verified.
Other OctoPrint versions may be compatible but are not claimed tested. Platforms other
than the current Linux test host remain untested. No real hardware or production Home
Assistant test has been performed. See the development report for current schema and
browser evidence.
