# Development report

Date: 2026-11-27. Initial snapshot: 0.1.0.dev0; current development build: 0.1.0.dev5.
This code was developed with AI assistance. The following software evidence does not
substitute for independent human review or the complete physical-device test plan.

## Real-hardware use reported by the project owner

The project owner confirms successful operation of the development builds on their
real hardware. This practical result is recorded separately from the automated tests,
which use synthetic HID. A complete record of hardware/software versions and the
individual H01–H09 observations remains pending; successful everyday use does not
establish every fault, restart or recovery case in that plan.

## Dev5 Python minimum change

The minimum supported interpreter is now Python 3.11. Package and OctoPrint plugin
metadata, the Python/MQTT matrix, registry fixture and installation checks use the
same requirement. The lockfile no longer contains the Python 3.9 tooling branches.
OctoPrint dependency constraints are unchanged; the remaining host advisories are
still blocking. No host dependency has been forced or overridden. The earlier
Python 3.9 results below apply to dev0–dev4 only.

Actual local dev5 runs pass 248 unit/contract tests each on Python 3.11.15
(MQTT 0.8.20) and Python 3.13.12 (MQTT 0.8.19), with 91.17% branch-inclusive
coverage. Ruff and both matching mypy targets pass. The regular Python 3.11
resolution still reports 14 advisory entries across Tornado and zeroconf.
No advisory exception has been added. Four actual broker/service/authorization
cases pass on Python 3.11. A fresh Python 3.11 environment also installs the wheel
with official OctoPrint 2.0.2 through normal dependency resolution: `uv pip check`
passes for all 80 installed packages, and the installed entry point loads outside
the source tree. This is installation evidence, not a full 2.0.2 runtime contract.
The archive verifier now checks dependency consistency before adding test-only
upstream plugins, whose USB driver is intentionally replaced by synthetic HID.

## Dev4 evidence before the Python minimum change

The current core, pinned upstream contracts and test-service diagnostics pass 248 tests
in every Python/MQTT matrix combination. The local Python 3.13 run has 91.12%
branch-inclusive coverage; CI enforces at least 85%. Ruff, mypy,
TypeScript, ESLint, Prettier and five Vitest tests pass. Nine actual Home Assistant
2026.11.3 schema cases pass. All 83 English UI messages have compiled German
translations. New tests exercise sustained command/control fairness, command expiry
including lock waits, independent channel pacing, identity recovery across restart,
cache persistence failure, bounded teardown and live slow-call warning delivery.
An unchanged settings save also restores readiness after invalidation.

On 2026-11-27, actual Chromium journeys passed in English, German and a compact
viewport, including timing Save/Close, device grouping controls and light/dark host
themes. The separate read-failure journey also passed: four Python integration cases,
each using its own server and broker. All eleven actual Home Assistant checks passed,
including nine schemas, device migration to the shared printer and back, and the
HA-to-companion-to-original roundtrip. A real broker and installed OctoPrint plugins
also passed four service/authorization/missing-device cases on Python 3.13.
These exercises use synthetic HID; the owner's real-hardware use is recorded above.
The initial baseline below remains historical dev0/dev1 evidence.

## CI corrections — 2026-11-27

The first remote runs exposed test-environment and fixture problems:

- Mypy used a fixed Python 3.9 target with Python 3.13 dependencies containing newer
  syntax. Each matrix job now selects its matching target. The current minimum is
  Python 3.11; the earlier Python 3.9 results below are historical evidence.
- Ubuntu's AppArmor profile denied Mosquitto access to generated configurations.
  CI now places them inside the profile's permitted `conf.d` subtree, in disposable
  subdirectories, without disabling confinement or changing the system configuration.
  Early broker exits report the actual startup error instead of a generic timeout.
- Browser projects shared a server and inherited saved settings. Each language and
  viewport now starts its own independent server and broker.
- The HA migration test used deprecated device-registry dictionary indexing. It now
  uses the registry's supported `async_get` lookup while retaining the same assertions.

Four new regression cases cover broker startup failures, an explicit configuration
directory, process cleanup and preservation of unrelated files. The strict Python
dependency audit remains a separate failing gate; no advisory has been waived.
The repaired [GitHub Actions run](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/actions/runs/45968905277)
passes all four backend combinations, the browser job and the Home Assistant job.
Packaging also passes: wheel, sdist and curated ZIP content checks, nine controlled
contamination counterchecks, fresh installations, entry-point loading, real isolated
service checks and uninstall without a product-source fallback. All seven functional
jobs pass; only the two strict Python dependency audits fail with the documented
host-baseline advisories. The workflow's overall conclusion therefore remains failure.

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

A complete physical H01–H09 result record, independent human code/privacy/license
review, approved project license and public identities, actual update URLs, the
approved release image set, authorized beta and official registration remain open.
The update hook is inactive
without an approved source. The private source repository has been pushed and its
first GitHub Actions run completed with failures. No public release has been published.
The automated exercises described here use synthetic hardware; the owner's successful
physical-device use is recorded above. The release-readiness command deliberately
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
