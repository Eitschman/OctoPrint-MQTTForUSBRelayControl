# ADR 0011: Companion view model and Plugin Messages

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

Original MQTT-external state changes do not update its observable button array.

## Alternatives

Replacing original JS methods or polling its REST endpoint was rejected.

## Decision

Use the actual optional uSBRelayControlViewModel dependency, identity validation and observableArray.replace.

## Consequences and risks

Reapply the latest snapshot after delayed original REST updates. Own row snapshots are observables. No original class/function is replaced.
Preserve editable row observables during state messages. Recreate rendered rows only
when original metadata changes. On server reconnect reset the message revision gate
and ignore own HTTP responses captured before that reconnect.

## Reassessment

Revisit if the original frontend changes dependency naming, configuration identity or observable structure.
