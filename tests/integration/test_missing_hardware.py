"""Missing-device startup remains controlled in a disposable server."""

import os

import pytest

from tests.services import IsolatedOctoPrint, broker, wait_for

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SERVICE_TESTS") != "1", reason="Disposable services only"
)


def test_f22_p04_server_survives_missing_synthetic_device(tmp_path):
    with broker(tmp_path / "broker") as port:
        with IsolatedOctoPrint(tmp_path / "octoprint", port, hardware_available=False) as server:
            status = wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol"))
            assert status["relays"] == []
            assert not status["ready"]
            assert server.get("/api/version")["api"]
