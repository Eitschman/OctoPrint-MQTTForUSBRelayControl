# ADR 0008: Persistent instance and normalized channel identity

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

Names and list order can change; cloned filesystems copy settings.

## Alternatives

Name- or index-based identity would create duplicate entities after reorder.

## Decision

Use persistent instance UUID, normalized VID/PID and channel; require confirmed offline clone re-identification.

Device grouping is independent of those relay IDs. Since dev3, use the active
HomeAssistant Discovery plugin's exact `node_id` by default. This is the identifier
that plugin places in `device.ids`; its `node_name` supplies the default shared
name. Read only those settings through OctoPrint's enabled plugin lookup. A known
missing/disabled plugin uses the UUID-based companion device. Since dev4, transient
lookup/read errors and invalid values preserve the last validated identity/name,
saved atomically in the companion's `device-identity.json`. With no saved value,
fall back to a separate device and report the unavailable source. A new valid read
replaces the cache; failures to persist are visible but do not disable integration.
Manual/separate-device overrides bypass this fallback. Do not derive a shared
identifier from MQTT topics or display names.

`use_octoprint_device=false` explicitly keeps a separate device. A nonempty
`device_identifier` takes precedence over this option and automatic grouping.
Only the chosen identifier is published, so switching back does not retain a
second identifier that would permanently merge devices. Custom targets omit the
name unless explicitly overridden. Relay IDs, owned MQTT topics and ledger rules
remain unchanged; grouping changes republish the existing discovery configuration.

The additive defaults apply to existing pre-release settings. Manufacturer/model
data are not copied; an explicit shared name can compete with another publisher's
name. Device-based automations referencing the old standalone device need review.
The companion clone action cannot regenerate the other plugin's copied identity.

References checked on 2026-11-26:

- [HomeAssistant Discovery identity configuration](https://github.com/cmroche/OctoPrint-HomeAssistant/blob/master/octoprint_homeassistant/__init__.py)
- [Home Assistant MQTT device grouping](https://www.home-assistant.io/integrations/mqtt/#mqtt-device-configuration)
- [Home Assistant 2026.11.3 discovery device updates](https://github.com/home-assistant/core/blob/2026.11.3/homeassistant/components/mqtt/entity.py)

Schema and synthetic runtime contract tests pass; the new live grouping migration
journey remains pending where local sockets are unavailable. Source inspection
does not substitute for that runtime evidence.

## Consequences and risks

Clones cannot be detected automatically. Old copied identity is detached without any old-topic publication or deletion.

## Reassessment

Reassess if upstream exposes stable serial-number selection for identical VID/PID boards.
