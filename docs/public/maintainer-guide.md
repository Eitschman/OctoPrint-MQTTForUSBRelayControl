# Maintainer guide

Start with the [architecture](architecture.md), [API inventory](../api-inventory.md)
and ADRs. The deliberately narrow internal contract is USB Relay Control 1.0.0:
`on_after_startup`, `on_settings_save`, API selection and existing `Relay.state`.
Never use the original save handler to read state. The original plugin recreates
objects during save; generation and epoch checks must prevent stale control.

OctoPrint's known `time_this` wrappers are legitimate. Unknown wrappers must not be
silently removed. Teardown restores only attributes still owned by this adapter.
Retired bindings must be restored and removed on every reconstruction, including
failed saves. Their activity tokens must be disabled before any foreign wrapper is
left intact. Original atexit registrations independently retain cleanup callbacks;
do not unregister them to make a companion memory test pass. Isolate only the test
registry when proving that the companion itself releases references.
The hardware lock ends before observation delivery; hardware sequence numbers reject
out-of-order sink delivery. Do not acquire the hardware lock while holding a status
lock across a wait. A pending original reconstruction closes command gates until its
completion notification. Keep callbacks free of hardware access and transport waits.

Reproduce failures against the pinned source manifest before expanding support.
Document negative HID return, short/empty report, physical/logical inversion, both
write/read exceptions, reconnect epochs and ownership corruption independently.
When adding an upstream version, run real installed-plugin integration as well as
source probes: these exposed differences that fakes missed during development.

Discovery updates must persist ownership before publication. A True publish helper
return is not an ACK and must not erase tombstones. Never delete foreign discovery,
current discovery, or the old identity of an offline clone. Keep subscriptions
individually addressable: upstream unsubscribe variadic behavior is unsafe.
Dependency teardown must submit offline before dropping usable helpers. Reconnect
must also submit current unavailability when USB Relay Control is still disabled,
using compatible current MQTT helpers and the same identity/epoch gates. Never retain
an old command/state packet or publish on an old cloned identity.

Maintain English UI sources, complete German catalog and the German installation
guide. Run extraction/compilation and browser tests, inspect actual screenshots and
check the original plain-item observable array after delayed original responses.

Before each release: update the single `_version.py`, changelog and actual evidence;
review dependencies/advisories and all 14 ADRs; build wheel, sdist and curated source
ZIP; inspect their contents; install/uninstall from the archives in a fresh standard
environment. A release owner must approve license/attribution/real URLs, human review,
hardware evidence and beta/release actions. Current update hook returns an empty
configuration until those URLs are approved; it never points at an upstream project.
No public CI job publishes packages, source, screenshots or releases.

Stable versions use PEP 440 (`0.1.0`); test versions use `0.1.0a1`, `0.1.0b1` or
`0.1.0rc1`. Record the source archive SHA-256 and build metadata for local history.
Once version control is separately authorized, verify private exclusions before any
staging and retain the changelog. Archive builds/tests remain usable without Git.
