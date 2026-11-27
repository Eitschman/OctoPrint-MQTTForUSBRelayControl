# ADR 0003: Observe software events without polling

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

State must follow observed writes without periodic hardware reads.

## Alternatives

Interval polling and an external relay daemon were rejected.

## Decision

Read after writes and at startup, relevant changes, reconnect, birth and explicit reconciliation.

## Consequences and risks

Undisturbed hardware failure and external hardware changes are not universally detected.

## Reassessment

Reassess if the original plugin exposes a reliable public hardware event stream.
