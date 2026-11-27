"""Portable disposable loopback services. Never use a production base directory."""

import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except (requests.RequestException, ConnectionError, OSError):
            pass
        time.sleep(0.1)
    raise TimeoutError("The isolated service did not become ready")


@contextmanager
def broker(directory, control=None):
    binary = os.environ.get("MOSQUITTO_BINARY") or shutil.which("mosquitto")
    if not binary:
        raise RuntimeError("Install Mosquitto or set MOSQUITTO_BINARY for isolated broker tests")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    port = free_port()
    config_root = os.environ.get("MOSQUITTO_CONFIG_DIRECTORY") or directory
    with (
        tempfile.TemporaryDirectory(prefix="relay-broker-", dir=config_root) as config_directory,
        (directory / "mosquitto.log").open("w") as log,
    ):
        configuration = Path(config_directory) / "mosquitto.conf"
        configuration.write_text(
            f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n",
            encoding="utf-8",
        )
        process = subprocess.Popen([str(binary), "-c", str(configuration)], stdout=log, stderr=log)
        try:

            def listening():
                if process.poll() is not None:
                    details = (directory / "mosquitto.log").read_text(
                        encoding="utf-8", errors="replace"
                    )
                    raise RuntimeError(
                        f"The isolated broker {binary} exited with code "
                        f"{process.returncode}: {details[-2000:]}"
                    )
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return True

            wait_for(listening, 10)
            if control is not None:

                def restart():
                    nonlocal process
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
                    process = subprocess.Popen(
                        [str(binary), "-c", str(configuration)], stdout=log, stderr=log
                    )
                    wait_for(listening, 10)

                def pause():
                    process.terminate()
                    process.wait(timeout=10)

                control.update(restart=restart, pause=pause)
            yield port
        finally:
            process.terminate()
            process.wait(timeout=10)


class IsolatedOctoPrint:
    def __init__(self, base, broker_port, hardware_available=True, interpreter=None):
        self.interpreter = interpreter or sys.executable
        self.base = Path(base).resolve()
        if self.base.exists() and any(self.base.iterdir()):
            raise ValueError("The isolated OctoPrint directory must be empty")
        self.base.mkdir(parents=True, exist_ok=True)
        (self.base / ".mqtt-relay-isolated").touch()
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.key = secrets.token_hex(24)
        self.username = "relay-test-admin"
        self.password = secrets.token_urlsafe(32)
        self.session = requests.Session()
        self.session.headers["X-Api-Key"] = self.key
        self.process = None
        self.log = None
        self.environment = dict(
            os.environ,
            MQTT_RELAY_ISOLATED_TEST="1",
            PYTHONPATH=str(ROOT / "tests/fixtures/isolated") + os.pathsep + str(ROOT),
        )
        if not hardware_available:
            self.environment["MQTT_RELAY_TEST_NO_DEVICE"] = "1"
        configuration = {
            "server": {
                "firstRun": False,
                "onlineCheck": {"enabled": False},
                "pluginBlacklist": {"enabled": False},
            },
            "api": {"key": self.key},
            "accessControl": {"enabled": True},
            "plugins": {
                "_disabled": [
                    "announcements",
                    "tracking",
                    "discovery",
                    "achievements",
                    "softwareupdate",
                ],
                "pluginmanager": {
                    "repository": "http://127.0.0.1:1/disabled",
                    "notices": "http://127.0.0.1:1/disabled",
                },
                "softwareupdate": {"check_overlay": {}, "cache_ttl": 999999},
                "mqtt": {
                    "broker": {"url": "127.0.0.1", "port": broker_port, "protocol": "MQTTv311"},
                    "publish": {
                        "baseTopic": "isolated/",
                        "lwActive": True,
                        "lwTopic": "mqtt",
                        "eventActive": False,
                    },
                },
                "usbrelaycontrol": {
                    "usbrelay_configurations": [
                        {
                            "vendor": "16c0",
                            "product": "05df",
                            "relaynumber": "1",
                            "active_mode": "active_high",
                            "default_state": "default_off",
                            "name": "Synthetic work light with a long accessible name",
                            "icon": "fas fa-plug",
                        }
                    ]
                },
            },
        }
        (self.base / "config.yaml").write_text(yaml.safe_dump(configuration), encoding="utf-8")

    def start(self):
        self.log = (self.base / "test-server.log").open("w")
        command = [self.interpreter, "-m", "octoprint", "--basedir", str(self.base)]
        result = subprocess.run(
            command + ["user", "add", self.username, "--password", self.password, "--admin"],
            env=self.environment,
            capture_output=True,
            timeout=40,
        )
        if result.returncode:
            raise RuntimeError("Could not create the isolated test account")
        self.process = subprocess.Popen(
            command
            + ["serve", "--host", "127.0.0.1", "--port", str(self.port), "--iknowwhatimdoing"],
            env=self.environment,
            stdout=self.log,
            stderr=self.log,
        )
        wait_for(lambda: self.session.get(self.url + "/api/version", timeout=1).ok, 60)
        return self

    def get(self, path):
        response = self.session.get(self.url + path, timeout=10)
        response.raise_for_status()
        return response.json()

    def post(self, path, data):
        response = self.session.post(self.url + path, json=data, timeout=10)
        response.raise_for_status()
        return response.json() if response.content else None

    def close(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log:
            self.log.close()
        self.session.close()

    def __enter__(self):
        try:
            return self.start()
        except Exception:
            self.close()
            raise

    def __exit__(self, *args):
        self.close()
