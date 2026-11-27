# ADR 0010: Reject retained replay before hardware

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

Broker-retained commands may outlive user intent.

## Alternatives

Executing replayed commands can switch hardware during startup or reconnect.

## Decision

Require callback retained metadata to be exactly False before queuing and before execution.

Since dev4, also bound command age from receipt (default 5 seconds, configurable
1–60) and per-channel spacing after completion (default 0.25 seconds, configurable
0.1–10). Check age again inside the hardware transaction after lock acquisition.
The 128-entry queue preserves channel order; commands on other eligible channels
can pass waiting channels. A deadline condition wait wakes for eligibility, expiry
or a new event without hardware polling. Round-robin selection of controls,
commands and current-state publication prevents category starvation under load.
Original local actions retain their behavior.

## Consequences and risks

MQTT clears retain on live delivery to an existing subscriber; sender intent cannot be inferred beyond supplied metadata. Document retain=false publishers.

Expiry cannot measure upstream/broker delay before the callback or cancel a running
call. Waiting commands may expire under sustained load; counters expose expiry and
queue overflow. Per-channel pacing is not authentication or an electrical safety
guarantee. The shared MQTT plugin and its connection are unchanged.

## Reassessment

Reassess if helper metadata or MQTT subscription options provide stronger retain-origin evidence.
