# ADR 0006: Serialize hardware access and preserve current ordering

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

Local API operations and MQTT callbacks may overlap original reconfiguration.

## Alternatives

A lock only around the final state call leaves configuration selection unprotected.

## Decision

Share an RLock across API selection, state access and reconstruction; deliver observations outside it.

## Consequences and risks

A bounded worker isolates transport; hardware sequence numbers reject reordered observer delivery. Reconfiguration keeps command gates closed until completion.

## Reassessment

Reassess if upstream adds cancellation or its own shared transaction contract.
