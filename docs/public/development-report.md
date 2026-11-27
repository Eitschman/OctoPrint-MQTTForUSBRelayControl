# Development report

Date: 2026-11-26. Initial snapshot: 0.1.0.dev0; current local review build: 0.1.0.dev4.
This code was developed with AI assistance. The following software evidence does not
substitute for independent human review or authorized physical-device testing.

## Current dev4 evidence

The current core and pinned upstream contracts pass 244 tests on each of Python
3.9.25 and 3.13.12, with 91.12% branch-inclusive coverage on 3.9. Ruff, mypy,
TypeScript, ESLint, Prettier and five Vitest tests pass. Nine actual Home Assistant
2026.11.3 schema cases pass. All 83 English UI messages have compiled German
translations. New tests exercise sustained command/control fairness, command expiry
including lock waits, independent channel pacing, identity recovery across restart,
cache persistence failure, bounded teardown and live slow-call warning delivery.
An unchanged settings save also restores readiness after invalidation.

The new browser journey covers command timing Save/Close and light/dark number
inputs. Three variants are discovered and type-checked. Execution remains pending:
Chromium startup is denied by the current sandbox, and an attempted HA runtime
test fails at socket creation with `PermissionError`. No new dev4 real-server,
broker, HA runtime, hardware or full clean-environment installation result is
claimed. The successful installed-server/browser/runtime evidence below is
historical dev0/dev1 evidence; it does not automatically validate later changes.

## Initial dev0/dev1 implementation and exercises

The backend uses a narrow instance adapter, the original relay objects and the existing
OctoPrint-MQTT helpers. Every accepted command performs readback; requested state,
actual state and write/read failures remain distinct. Configuration reconstruction,
concurrent operations, stale callbacks, bounded shutdown and foreign wrappers have
regression coverage. No product code constructs an MQTT or USB client, polls devices
or calls another plugin through REST. Sync never invokes the original settings save.

The core and its pinned upstream contracts pass **148 tests on each of Python 3.9.25
and 3.13.12**. This includes 28 parameterized cases reproducing the 18 research probes.
Branch-inclusive coverage is **88.81%** overall, with all seven functional core modules
above 85%. Ruff, mypy and the five Vitest frontend-contract tests pass.

Actual installed OctoPrint 2.0.1, USB Relay Control 1.0.0 and MQTT 0.8.19/0.8.20 pass
all four Python/MQTT service combinations against a disposable real Mosquitto broker.
OctoPrint 1.11.2 was separately exercised as the package minimum. The tests explicitly
simulate the original plugin's HID boundary; they do not verify physical outputs.
Authorization, CSRF and startup with missing hardware use actual isolated servers.

Chromium exercises English and German at 1920×1080 and English at 768×900: external
MQTT ON updates both companion and original controls, original OFF publishes actual
OFF, Close discards edits and Save preserves them. A separate read-failure journey
shows Unknown and an explicit diagnostic. The settings layout was refined following
owner feedback, then rendered and tested again. Translations are compiled for all
53 UI messages. Screenshots use synthetic data and remain local review evidence.

Home Assistant 2026.11.3 runs in a separate Python 3.14.3 environment. Actual schemas
for switch, light and fan pass; a real HA/MQTT runtime exercises discovery, availability,
deletions and type replacement. An additional full-stack test calls HA's light service,
checks actual companion readback and original state, then checks original OFF in HA.
The latter waits for initial availability/state convergence before sending a command.
Optional actual HA frontend captures use a generated local-only test account.

Wheel, sdist and independently curated source ZIP pass archive selection/privacy checks
and nine deliberately contaminated-archive counterchecks. Each format is installed in
a fresh environment from public sources, its entry point loaded, an isolated server
started with synthetic and missing hardware, and the plugin uninstalled. The installed
suite has no product-source fallback and no private agent/configuration dependencies.
Official registry-validator tests use checksummed synthetic fixtures and deliberate
missing metadata/images. The actual project draft remains invalid until the owner
approves identities, license and real project URLs.

## Runtime findings incorporated

- Recognize legitimate OctoPrint timing wrappers narrowly; reject unknown wrappers.
- Read nested plugin settings by leaf because dictionary access may omit defaults.
- Use the actual optional original dependency `uSBRelayControlViewModel`.
- Publish at QoS 0 with offline queueing disabled. A real broker restart reproduced
  Paho replay of earlier QoS-1 publications even when the plugin queue was disabled.
  This correction prevents that tested history path; it does not guarantee delivery.
- Omit the obsolete optional light discovery `schema: default` field for current HA.
- Preserve stale-message gates across server reconnects and asynchronous responses.

## Remaining release evidence

The strict dependency advisory gate currently fails: 121 advisory entries in nine
Python 3.9 packages and 14 in two Python 3.13 packages. Repeated advisory IDs are not
additional distinct vulnerabilities. The Node audit reports no findings. See the
[dependency review](dependency-review.md); no blanket risk acceptance is claimed.

Physical H01–H09, independent human code/privacy/license review, approved project
license and public identities, actual update URLs, the approved release image set,
authorized beta and official registration remain open. The update hook is inactive
without an approved source. No publication, remote CI run, production change or
physical relay operation was performed. The release-readiness command deliberately
rejects this unapproved development snapshot.

## Review follow-up: 0.1.0.dev1

Seven targeted counterprobes reproduced two review findings in dev0: retained online
availability could survive dependency teardown, and retired relay bindings accumulated
in the adapter manifest. They pass after the fixes. Seventeen added regression cases
also cover offline/reconnect, current-helper compatibility, identity guards, publish
failure, failed reconstruction and foreign wrappers. Both Python targets now pass
165 tests; branch-inclusive coverage is 89.49% on Python 3.9.

The adapter prunes obsolete references under its hardware lock. Garbage-collection
checks explicitly clear only the synthetic upstream atexit registry: the real original
plugin independently retains cleanup callbacks and remains unchanged. A real local
broker/server counterprobe observes online before original-plugin disable, offline
after disable, and retained offline on a fresh subscription. No physical hardware or
productive instance is used, and no delivery guarantee is inferred.
