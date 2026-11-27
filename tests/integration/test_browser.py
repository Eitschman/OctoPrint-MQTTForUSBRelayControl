"""Run browser tests against an owned, newly created local OctoPrint instance."""

import os
import shutil
import subprocess
import sys

import pytest

from tests.services import ROOT, IsolatedOctoPrint, broker, wait_for

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_BROWSER_TESTS") != "1",
        reason="Set RUN_BROWSER_TESTS=1 for disposable browser integration",
    ),
]


@pytest.mark.parametrize("project", ["desktop", "desktop-de", "compact"])
def test_i01_browser_settings(tmp_path, project):
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise RuntimeError("Install pnpm and the locked public browser dependencies")
    with (
        broker(tmp_path / "broker") as port,
        IsolatedOctoPrint(tmp_path / "octoprint", port) as server,
    ):
        status = wait_for(
            lambda: (
                value
                if (value := server.get("/api/plugin/mqttforusbrelaycontrol"))["relays"]
                else None
            )
        )
        identity = status["relays"][0]["id"]
        server.post(
            "/api/settings",
            {
                "plugins": {
                    "mqttforusbrelaycontrol": {
                        "integration_enabled": True,
                        "relays": {
                            identity: {"enabled": True, "entity_type": "light", "display_name": ""}
                        },
                    }
                }
            },
        )
        wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
        instance_uuid = server.get("/api/settings")["plugins"]["mqttforusbrelaycontrol"][
            "instance_uuid"
        ]
        environment = dict(
            os.environ,
            TEST_BASE_URL=server.url,
            TEST_USERNAME=server.username,
            TEST_PASSWORD=server.password,
            TEST_PYTHON=sys.executable,
            TEST_BROKER_PORT=str(port),
            TEST_COMMAND_TOPIC=f"isolated/usbrelay/{instance_uuid}/16c0-05df/1/set",
        )
        result = subprocess.run(
            [pnpm, "test:browser", f"--project={project}"], cwd=ROOT, env=environment, timeout=160
        )
        assert result.returncode == 0, "The browser suite failed; inspect its sanitized output"


def test_ui04_actual_read_failure(tmp_path):
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise RuntimeError("Install the public pnpm test tool")
    with broker(tmp_path / "broker") as port:
        server = IsolatedOctoPrint(tmp_path / "octoprint", port)
        server.environment["MQTT_RELAY_TEST_READ_FAILURE"] = "1"
        with server:
            wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["relays"])
            environment = dict(
                os.environ,
                TEST_READ_FAILURE="1",
                TEST_BASE_URL=server.url,
                TEST_USERNAME=server.username,
                TEST_PASSWORD=server.password,
            )
            result = subprocess.run(
                [pnpm, "exec", "playwright", "test", "--project=desktop"],
                cwd=ROOT,
                env=environment,
                timeout=90,
            )
            assert result.returncode == 0, "The read-failure browser test failed"
