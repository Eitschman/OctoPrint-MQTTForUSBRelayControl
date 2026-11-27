# Changelog

## 0.1.0.dev5 — unreleased

- Require Python 3.11 or later in package metadata, OctoPrint compatibility,
  development tools and CI. Python 3.9 and 3.10 are no longer supported.
- Use current pytest and pip on every supported test interpreter. Existing
  OctoPrint dependency advisory findings remain open and strictly checked.

## 0.1.0.dev4 — unreleased

- Rotate reconciliation, commands and current-state publication fairly under load.
- Expire queued MQTT commands after 5 seconds by default, including a final check
  after acquiring the hardware lock. Space commands on each channel by at least
  250 ms after completion. Both limits are configurable; other channels and state
  publication can proceed during the channel wait. Original buttons are unchanged.
- Keep the last validated optional device identity on transient read failures,
  including after restart, in an atomic companion-owned cache. Explicit overrides
  and known optional-plugin removal/disable still take precedence.
- Warn once when an upstream hardware call exceeds 2 seconds; expose operation,
  duration, queue/expiry/overflow counters and assignment source in English/German.
  Bound adapter teardown and require restart if safe restoration fails. No attempt
  is made to cancel or retry a running hardware call.
- Clarify that controller readback does not confirm power at the connected load.

## 0.1.0.dev3 — unreleased

- Join the existing HomeAssistant Discovery device by default, using its exact
  device identifier and name when available. Missing/invalid optional settings
  fall back to the separate companion device.
- Add a separate-device option and a manual device identifier override. Preserve
  relay unique IDs and MQTT topics across assignment changes; do not merge the
  companion identifier into the shared device or change foreign configuration.
- Reevaluate optional identity/name changes and plugin lifecycle events without
  rebuilding the relay adapter. Show the effective device identifier in diagnostics.
- Add English/German controls, instructions and grouping/schema/migration regressions.

## 0.1.0.dev2 — unreleased

Local appearance and naming fixes, 2026-11-26.

- Inherit text and form-control colors from the active OctoPrint theme. Use neutral
  translucent surfaces and borders in both light and dark settings dialogs.
- Default the Home Assistant device name to OctoPrint-MQTT's base topic without
  trailing slashes. An explicit device name takes precedence; a custom companion
  MQTT prefix does not change this fallback. Device and entity identifiers stay stable.
- Clarify the fallback in English and German settings and installation documentation.
- Add naming regressions and browser assertions for light/dark host themes, including
  an opposing operating system color scheme. Browser execution remains pending in
  the current restricted environment, which denies sockets and Chromium startup.

## 0.1.0.dev1 — unreleased

Local review fixes, 2026-11-26. Existing dev0 installations are not changed automatically.

- Submit retained offline availability before dependency teardown. If the dependency
  was disabled while disconnected, submit the current unavailable state after reconnect
  through compatible current OctoPrint-MQTT helpers, without the offline queue.
- Restore and remove obsolete relay wrappers after original-object reconstruction,
  including failure paths; preserve foreign wrappers and make retired callbacks inert.
- Add before/after regression probes, bounded-manifest and isolated garbage-collection
  checks, plus a real-broker test for retained offline availability after original disable.
- Upstream cleanup callbacks registered with atexit independently retain original
  objects; this change does not modify those registrations or claim to remove them.

## 0.1.0.dev0 — unreleased

Local development snapshot, implemented on 2026-11-26. No public release or hardware
validation is claimed. Artifact checksums and actual local verification are recorded
separately; version-control initialization is not required for archive builds.

- Event-driven relay state adapter with verified MQTT writes and explicit unknown/error states.
- Existing MQTT helpers only, retained replay rejection, QoS 0 and no offline publish queue.
- Binary Switch/Light/Fan discovery, owned durable deletions and confirmed offline clone identity.
- Original-object reconstruction, dependency replacement, reconnect and LWT availability gates.
- Companion browser updates, saved settings, English UI and maintained German translation.
- Portable Python/Node tests, real isolated broker/OctoPrint/HA checks and curated packaging tools.
- English user/maintainer documentation, German installation guide and 14 architecture decisions.

Outstanding release gates include owner-approved license/identity/URLs, dependency-advisory
assessment, independent human review, authorized physical hardware tests, beta and publication.
