# ADR 0004: Reversible instance runtime adapter

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

The original plugin has no suitable public write observer.

## Alternatives

Global class patches and permanent source edits affect unrelated instances.

## Decision

Wrap only selected existing instance attributes and record original ownership.
After registry reconstruction, restore and remove bindings for retired relay objects
under the hardware lock. Retained callbacks have per-binding activity tokens; foreign
wrappers are preserved while the retired companion callback becomes inert.

## Consequences and risks

Known OctoPrint timing wrappers are accepted; foreign wrappers fail compatibility or limit safe teardown.
The manifest holds only original entry points and current relay bindings. Upstream
atexit cleanup registrations independently retain relay objects; they remain untouched.
Garbage-collection tests isolate that upstream registry and do not claim complete
real-runtime object collection.

## Reassessment

Revisit whenever USB Relay Control changes object construction or state signatures.
