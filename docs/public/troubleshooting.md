# Troubleshooting

| Symptom | Meaning and action |
| --- | --- |
| Last Will prerequisite | Enable the existing MQTT plugin's Last Will yourself and reconnect; the companion cannot provide reliable abrupt-disconnect availability without it |
| Unknown connection | Wait for a connection message or retained LWT; if LWT is not retained, reconnect the existing MQTT plugin |
| Unknown relay state | The read failed or returned an unexpected value; check original USB Relay Control, then use Read current states |
| Target differs from actual | The write did not yield the requested physical state; no automatic write retry is performed |
| Unsupported version/method | Runtime contract differs; leave integration off and provide sanitized versions for compatibility investigation |
| No relay rows | Configure the original plugin first; resolve invalid VID/PID, channel, active mode or duplicate normalized channel errors |
| Original buttons stale | Check frontend compatibility; the original `uSBRelayControlViewModel` and its observables must be available; restart after installing assets |
| Discovery remains after uninstall | Offline removal cannot reach the broker; retry recorded owned tombstones or remove those exact retained topics manually |
| Ledger corruption | Stop integration, preserve the file for diagnosis and repair ownership deliberately; do not replace it with arbitrary empty ownership data |
| Restart required after wrapper change | Another wrapper replaced an owned attribute; safe teardown leaves that foreign attribute intact |
| Worker blocked | An upstream call has no cancellation API; restart after investigating the original hardware/plugin, without claiming that timeout cancelled the operation |
| Queued commands expire | The maximum command age includes waiting for the channel interval and hardware lock. Check queue/expiry/overflow counters and operation duration; a running call cannot be cancelled |
| Commands arrive faster than a channel switches | The companion spaces MQTT commands per channel after completion (default 250 ms). Waiting commands may expire after 5 seconds; both limits are configurable in advanced settings |
| Cached device assignment | Optional identity lookup/read failed or returned an invalid value. The last validated identity is retained in companion data; a valid new source replaces it. Explicit overrides and known plugin disable/removal take precedence |
| Assignment cache write failed | Current grouping is usable but durable recovery after restart is unavailable; check write access to the companion data folder |
| Hardware warning after 2 seconds | The one-shot diagnostic does not cancel the call. Current/last durations are sampled on status updates; slow counts persist only for the current adapter binding |

No polling or universal USB fault detection is provided. Check the current actual
state and error fields; a saved target is not proof of hardware state. Include
sanitized plugin/Python versions and the outcome, not broker credentials or server
configuration dumps, when requesting support.
