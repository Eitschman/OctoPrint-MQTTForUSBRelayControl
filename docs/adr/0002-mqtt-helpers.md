# ADR 0002: Reuse existing MQTT helpers

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

A second MQTT connection is prohibited.

## Alternatives

A new Paho client or inter-plugin REST would bypass the existing connection.

## Decision

Use only mqtt_publish, mqtt_subscribe and topic-specific mqtt_unsubscribe.

## Consequences and risks

Subscription QoS is effectively 0; publish acceptance is not a delivery ACK. No offline queue is used.
Publish explicitly requests QoS 0. An actual MQTT 0.8.19 reconnect reproduced historical
QoS-1 in-flight retransmission by the shared client even with offline queueing disabled.
The companion cannot retract an already submitted packet through the helper contract.

## Reassessment

Reassess if upstream adds acknowledged publication or changes helper signatures.
