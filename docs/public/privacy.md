# Privacy and security boundaries

The companion has no telemetry, external account, cloud service or analytics. It
uses the broker already configured in OctoPrint-MQTT. It does not read or display
broker passwords. No credentials are included in source, tests or artifacts.

Discovery and MQTT state can reveal instance identifiers, VID/PID, channel names,
state and availability. Retained discovery remains at the broker until removed.
Apply broker authentication, topic ACLs and transport protection in the existing
MQTT plugin. Anyone allowed to publish a fresh valid command can operate an exposed
relay. Retained replay rejection is not an authorization mechanism.

Command expiry and per-channel pacing limit queued work; they are not broker
authentication and cannot cancel an operation already running. A last validated
optional HomeAssistant Discovery identity/name is stored as `device-identity.json`
in the companion's data folder for recovery from transient source read failures.
It contains no broker credentials and does not modify foreign settings. Identity,
assignment source, queue counts and operation durations are included in the own
administrator status API and Plugin Messages.

Own settings and actions require OctoPrint administrator authorization and its normal
API authentication/CSRF checks. The product exposes no separate hardware command API.
Logs use English diagnostics without configuration dumps, credentials or raw payloads.
Test accounts and tokens are newly generated for disposable loopback instances;
traces, video and request-body recording are disabled. Test artifacts stay local.

Private development launchers, agent rules, planning, environment files, test server
directories and credentials are excluded from curated source and build artifacts.
An archive content gate verifies this independently of ignore rules.
