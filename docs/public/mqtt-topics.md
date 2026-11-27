# MQTT contract

For instance UUID `12345678-1234-4234-8234-123456789abc`, VID `16c0`, PID `05df`,
channel 1 and prefix `octoPrint`, runtime topics are:

| Topic suffix after `octoPrint/usbrelay/<uuid>/16c0-05df/1/` | Direction | Payload |
| --- | --- | --- |
| `set` | inbound | exact ASCII `ON` or `OFF` |
| `state` | outbound | verified `ON` or `OFF`; unknown produces no invented state |
| `availability` | outbound | `online` or `offline` |

The UUID is persistent. The stable unique ID uses UUID hex, normalized four-digit
VID/PID and channel. Discovery topics are
`<discovery_prefix>/<switch|light|fan>/<unique_id>/config`.

Inbound payloads are bounded, case-sensitive and do not support TOGGLE. A callback
must explicitly carry `retained=False`. Retained replay and missing metadata are
rejected before queuing and again before a hardware transaction. MQTT delivers a
new live retained publish to an existing subscriber with its retain flag cleared;
the upstream helper cannot reveal the sender's original retain intent. Publishers
must use retain=false. The replay protection applies to the metadata actually
provided by MQTT and the existing helper.

The companion queue holds at most 128 commands. It drops new commands on overflow
and counts the rejection. `command_max_age` defaults to 5 seconds (range 1–60);
expired commands are discarded before writing, including after waiting for the
original hardware lock. This age starts when the companion receives the callback;
it cannot detect time a message spent elsewhere before delivery.
`command_min_interval` defaults to 0.25 seconds (range 0.1–10), measured per channel
after command completion. Commands wait in order for that channel or expire; other
channels, reconciliation and state publication continue. They are not merged,
toggled or automatically retried. Condition deadline waits add no hardware polling.
A running upstream operation cannot be cancelled by either limit. The original
plugin's local actions bypass these companion MQTT limits. Queue and expiry counts
are process-local diagnostics, not broker acknowledgements.

Example retained discovery for a separate companion device on
`homeassistant/light/12345678123442348234123456789abc_16c0_05df_1/config`:

```json
{
  "name": "Enclosure light",
  "unique_id": "12345678123442348234123456789abc_16c0_05df_1",
  "command_topic": "octoPrint/usbrelay/12345678-1234-4234-8234-123456789abc/16c0-05df/1/set",
  "state_topic": "octoPrint/usbrelay/12345678-1234-4234-8234-123456789abc/16c0-05df/1/state",
  "payload_on": "ON",
  "payload_off": "OFF",
  "optimistic": false,
  "retain": false,
  "qos": 0,
  "availability_mode": "all",
  "availability": [
    {"topic": "octoPrint/mqtt", "payload_available": "connected", "payload_not_available": "disconnected"},
    {"topic": "octoPrint/usbrelay/12345678-1234-4234-8234-123456789abc/16c0-05df/1/availability", "payload_available": "online", "payload_not_available": "offline"}
  ],
  "device": {"identifiers": ["mqttforusbrelaycontrol_12345678123442348234123456789abc"], "name": "Test printer"}
}
```

By default, an active HomeAssistant Discovery plugin supplies the shared device's
exact `node_id` and optional `node_name`. Only the `device` mapping changes; the
relay unique ID and all topics above remain unchanged. `use_octoprint_device=false`
keeps a separate companion device. A nonempty `device_identifier` overrides both
modes; its letter case is preserved. Custom targets omit `device.name` unless an
explicit `device_name` is set. No companion identifier is appended to the shared
device, so choosing separate grouping again does not permanently merge devices.
Missing/invalid optional identity falls back to the separate device. Settings,
optional-plugin lifecycle events, reconnect and HA birth reevaluate the assignment.

The Light schema is intentionally omitted: current HA defaults to its basic Light
schema, and older HA defaults to the original schema. Switch and Fan use the same
binary fields on their respective discovery domain. No unsupported capability is added.

All companion outbound state, availability, discovery and empty-string deletion
messages request retained storage and QoS 0 with `allow_queueing=False`. This also avoids
QoS-1 in-flight retransmission of historical states by the shared client after reconnect.
Subscription
QoS is effectively 0 through the upstream helper. A True helper result means the
submission was accepted locally, not that a broker or Home Assistant received it.
No exactly-once or guaranteed delivery claim is made; failed writes are not retried.

Disconnect invalidates queued commands and historical pending output. Reconnect
reads current states, submits current discovery and required owned tombstones, then
reports channel availability. There is no offline publish queue or replayed state
history. HA birth causes read-only current-state/discovery reconciliation.

Availability uses `all`: the existing LWT topic expects `connected`/`disconnected`,
and the channel topic expects `online`/`offline`. Abrupt disconnect detection follows
the broker's keepalive behavior. No polling means undisturbed hardware faults can
remain undetected until an observed operation or reconciliation.

Read failures publish availability `offline` without fabricating a state. Write errors
or a target/actual mismatch also mark the channel offline while preserving any actually
read state. Diagnostics distinguish both errors even if they occur together. The
original driver discards HID write return codes; a matching readback confirms the
observed state, not successful acknowledgement of every lower-level USB packet.

Removing a channel, changing its HA domain/prefix or disabling exposure stores owned
retirement topics durably and submits empty retained discovery payloads. `{}` is not a
deletion. Tombstones remain pending after helper acceptance because it supplies no
broker ACK. Reconciliation submits them again; reactivated current topics are protected.
Offline uninstall cannot remove retained broker data; retain the old topic inventory
and perform separately reviewed cleanup once connected. Never delete foreign topics.
