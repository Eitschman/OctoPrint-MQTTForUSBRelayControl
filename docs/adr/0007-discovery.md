# ADR 0007: Minimal binary Home Assistant discovery

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

The physical channels provide binary control only.

## Alternatives

Advertising brightness, speed or optimistic state would invent capability.

## Decision

Publish switch, default-schema light or fan with exact ON/OFF, retain=false commands and verified state.

## Consequences and risks

Persist owned discovery intent atomically; retain empty-string tombstones after helper acceptance.

## Reassessment

Revalidate against actual Home Assistant schemas when discovery fields change.
