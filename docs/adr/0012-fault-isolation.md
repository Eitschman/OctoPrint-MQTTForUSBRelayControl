# ADR 0012: Preserve original behavior under companion faults

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

Local original controls must remain usable when MQTT or observers fail.

## Alternatives

Propagating companion publication errors through successful local writes was rejected.

## Decision

Preserve original return and exception identity; isolate observer/readback/transport errors and discard stale epochs.

## Consequences and risks

Write/read errors remain separate. No automatic write retry. A blocked upstream operation may require restart after bounded shutdown.

Since dev4, serialized upstream reads/writes/configuration record current/last/
longest duration and slow counts. A one-shot timer warns after 2 seconds. It never
touches hardware or cancels the upstream call; notification runs outside the
monitor lock. Failed diagnostic timer creation must not prevent the original
call. Displayed durations are sampled on events or explicit status requests.
Adapter teardown waits at most 2 seconds for its lock. Failure leaves wrappers
inactive and gates companion rebinding until restart, without claiming the call
has ended. Readback confirms controller bits, not electrical load power.

## Reassessment

Reassess with upstream timeout/cancellation support or a changed exception contract.
