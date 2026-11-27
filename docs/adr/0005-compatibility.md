# ADR 0005: Fail closed on unknown upstream contracts

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

The adapter intentionally depends on internal methods and frontend arrays.

## Alternatives

Assuming arbitrary versions compatible can silently address stale objects.

## Decision

Check versions, signatures, known wrapper code, collection shape and browser observables.

## Consequences and risks

USB 1.0.0 and MQTT 0.8.19/0.8.20 are primary targets; frontend compatibility is reported separately.

## Reassessment

Expand support only after pinned contract and installed-plugin tests pass.
