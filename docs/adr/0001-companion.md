# ADR 0001: Separate companion plugin

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

The original relay and MQTT plugins already own hardware and transport.

## Alternatives

Forking either plugin would duplicate maintenance and require persistent changes.

## Decision

Reuse existing instances through a small companion.

## Consequences and risks

Original ownership remains intact; internal contracts still require explicit compatibility checks.

## Reassessment

Reconsider only if upstream offers equivalent public change notifications.
