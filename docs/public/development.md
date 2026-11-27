# Portable development and verification

Install Python 3.9+ and uv from their public distributions, plus Node.js 24+ and the
pnpm version declared in package.json. No version-control initialization is necessary
for any local command. `CHANGELOG.md`, versioned source archives and the development
report provide a local release history until a repository is explicitly authorized.

```sh
uv sync --group dev
uv run python tools/prepare_upstream.py
uv run pytest tests/unit tests/integration/test_upstream_contracts.py
uv run ruff check octoprint_mqttforusbrelaycontrol tests tools
uv run mypy octoprint_mqttforusbrelaycontrol
uv run pytest tests/unit --cov=octoprint_mqttforusbrelaycontrol --cov-fail-under=85
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm lint
pnpm format:check
```

Initial source preparation explicitly downloads pinned public upstream files and
verifies SHA-256. Normal tests do not download source or access real USB hardware.
Tests that require source fixtures fail with a preparation instruction when absent.
Install test-only plugin revisions into the selected isolated interpreter:

```sh
uv run python tools/install_upstream.py --mqtt-version 0.8.20
```

This uses pip with `--no-deps` to avoid installing a USB driver. The locked development
group supplies the needed OctoPrint/MQTT dependencies. Repeat with 0.8.19 in a separate
environment or replace the test MQTT package deliberately. Re-run the contract suite
on both Python 3.9 and 3.13. A dependency sync may remove packages installed outside
the lock; use an inexact sync deliberately when preserving installed test plugins.
Run mypy with `--python-version 3.9` in the Python 3.9 environment and
`--python-version 3.13` in the Python 3.13 environment. The latter contains dependency
versions with newer syntax; the CI matrix checks both targets independently.

## Disposable services and browser

Install the public Mosquitto executable using your platform's standard package
manager, or provide its path through `MOSQUITTO_BINARY`. This is test-only. The
fixtures create a new empty base directory, generate independent accounts/tokens,
listen only on 127.0.0.1 and terminate their own subprocesses afterwards. They reject
an existing non-empty base directory. No production target is accepted.
On hosts that restrict broker configuration access, set `MOSQUITTO_CONFIG_DIRECTORY`
to an empty test directory that Mosquitto may read and the test user may write.
Each broker creates and removes its own configuration subdirectory there; logs remain
in the test result directory. CI prepares a dedicated directory under `/etc/mosquitto`
and selects the apt-installed executable explicitly. No system broker configuration
is changed and no host confinement is disabled.

```sh
RUN_SERVICE_TESTS=1 uv run pytest tests/integration/test_services.py tests/integration/test_authorization.py tests/integration/test_missing_hardware.py
PLAYWRIGHT_BROWSERS_PATH=artifacts/browsers pnpm exec playwright install chromium
RUN_BROWSER_TESTS=1 PLAYWRIGHT_BROWSERS_PATH=artifacts/browsers uv run pytest tests/integration/test_browser.py -s
```

The Python fixture passes `TEST_BASE_URL`, `TEST_USERNAME`, `TEST_PASSWORD`,
`TEST_PYTHON`, `TEST_BROKER_PORT` and `TEST_COMMAND_TOPIC` through the child environment.
The browser validates a plain loopback URL with an explicit port before authentication;
missing credentials fail without printing values. Each test has an independent browser
context. Tests never search personal credential stores or existing server configuration.
Each browser project also gets a fresh server and broker, so saved settings from one
language or viewport cannot become another project's starting state.
The test publisher is a separate test-only MQTT client; the product has no MQTT client.
No traces, request-body dumps, videos or authentication screenshots are captured.
Screenshots contain synthetic settings, relay controls or disposable Home Assistant pages and remain local artifacts.

## Packaging

```sh
uv run python tools/update_translations.py
uv run python -m build --outdir artifacts/dist
uv run python tools/check_artifact.py artifacts/dist/*.whl artifacts/dist/*.tar.gz
uv run python tools/export_public_source.py artifacts/dist/local-source.zip
uv run python tools/verify_artifact_negatives.py artifacts/dist/*.whl artifacts/dist/*.tar.gz artifacts/dist/local-source.zip
uv run python tools/verify_installation.py --source artifacts/dist/local-source.zip --artifacts artifacts/dist/*.whl artifacts/dist/*.tar.gz artifacts/dist/local-source.zip
```

Wheels select the plugin package/assets; sdists select explicit source and test files.
Curated ZIP creation uses an independent allowlist. The archive gate rejects private
paths, renamed private-content canaries, personal filesystem paths, key material and
unsafe archive links. Ignore rules alone are insufficient. Builds are local test
artifacts until license, identities, real URLs and release readiness are approved.

A blocked upstream hardware call cannot be interrupted safely. Shutdown has a bounded
worker join and reports that restart is required rather than pretending to cancel it.

## Optional actual Home Assistant and registry contracts

The HA target has its own interpreter and dependencies, separate from OctoPrint:

```sh
uv venv artifacts/ha --python 3.14
uv pip install --python artifacts/ha/bin/python homeassistant==2026.11.3 paho-mqtt==2.1.0 pytest==9.2.0
# Prepare an independent OctoPrint interpreter for the full roundtrip.
UV_PROJECT_ENVIRONMENT=artifacts/octoprint uv sync --locked --python 3.13 --group dev
UV_PROJECT_ENVIRONMENT=artifacts/octoprint uv run python tools/install_upstream.py --mqtt-version 0.8.20
RUN_HA_TESTS=1 TEST_OCTOPRINT_PYTHON="$PWD/artifacts/octoprint/bin/python" artifacts/ha/bin/python -m pytest tests/ha
# Optional: also capture actual disposable HA pages with the installed Chromium.
RUN_HA_TESTS=1 RUN_HA_BROWSER_TESTS=1 TEST_OCTOPRINT_PYTHON="$PWD/artifacts/octoprint/bin/python" PLAYWRIGHT_BROWSERS_PATH=artifacts/browsers artifacts/ha/bin/python -m pytest tests/ha/test_full_stack.py
uvx --python 3.13 --with python-frontmatter --with colorama --with voluptuous --with 'ruamel.yaml<0.18' --with packaging --with requests --with click python tools/validate_registry_fixtures.py --prepare
pnpm licenses list --json > artifacts/node-license-metadata.json
uv run python tools/dependency_inventory.py artifacts/dependency-licenses.json --node-metadata artifacts/node-license-metadata.json
```

The registry command checks synthetic fixtures against a checksummed official validator;
it does not submit a listing. Missing-image existence also needs an independent check.
Read the [dependency review](dependency-review.md): the strict advisory gate currently
reports unresolved host baseline findings. `tools/check_release_readiness.py` deliberately
fails while actual release approvals, license, URLs and evidence remain absent.
