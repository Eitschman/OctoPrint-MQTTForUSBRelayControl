# ADR 0009: Combine existing Last Will and channel availability

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

The companion cannot supply its own MQTT Last Will.

## Alternatives

Assuming online from cached state or changing another plugin setting was rejected.

## Decision

Require existing enabled LWT and availability_mode=all with a separate channel topic.
Submit owned offline availability before dependency teardown while a usable helper
exists. If teardown happened while disconnected, reconcile unavailable state after
reconnect through compatible current helpers even when the relay plugin stays disabled.
This temporary helper facade creates no MQTT client or connection.

## Consequences and risks

Every submission remains identity/epoch/connection gated and never queued offline;
helper acceptance is not a delivery guarantee. Missing LWT gates commands/discovery. Abrupt disconnect recognition follows broker keepalive; read failure is unavailable.

## Reassessment

Reassess if the existing MQTT plugin adds an explicit public connection-state helper.
