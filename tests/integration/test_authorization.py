"""Actual authentication, permissions and CSRF checks on an owned local server."""

import os
import secrets
from urllib.parse import unquote

import pytest
import requests

from tests.services import IsolatedOctoPrint, broker

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SERVICE_TESTS") != "1", reason="Disposable services only"
)


def test_s04_v15_authorization_csrf_and_log_redaction(tmp_path):
    with broker(tmp_path / "broker") as port:
        with IsolatedOctoPrint(tmp_path / "octoprint", port) as server:
            viewer_password = secrets.token_urlsafe(32)
            endpoint = server.url + "/api/plugin/mqttforusbrelaycontrol"
            with requests.Session() as session:
                assert session.get(endpoint, timeout=10).status_code in (401, 403)
                session.get(server.url + "/", timeout=40).raise_for_status()
                token = next(
                    unquote(value)
                    for name, value in session.cookies.items()
                    if name.startswith("csrf_token")
                )
                login = server.url + "/api/login"
                credentials = {"user": server.username, "pass": server.password}
                assert session.post(login, json=credentials, timeout=10).status_code in (400, 403)
                session.headers["X-CSRF-Token"] = token
                assert session.post(
                    login,
                    json={"user": server.username, "pass": "invalid-disposable-password"},
                    timeout=10,
                ).status_code in (401, 403)
                session.post(login, json=credentials, timeout=10).raise_for_status()
                assert session.get(endpoint, timeout=10).status_code == 200
                token = next(
                    unquote(value)
                    for name, value in session.cookies.items()
                    if name.startswith("csrf_token")
                )
                session.headers.pop("X-CSRF-Token")
                assert session.post(
                    endpoint, json={"command": "resync"}, timeout=10
                ).status_code in (400, 403)
                session.headers["X-CSRF-Token"] = token
                assert (
                    session.post(endpoint, json={"command": "resync"}, timeout=10).status_code
                    == 200
                )
            # The user manager reloads through the server API, so create the viewer there as admin.
            server.post(
                "/api/access/users",
                {
                    "name": "relay-test-browser-viewer",
                    "password": viewer_password,
                    "active": True,
                    "groups": ["users"],
                },
            )
            with requests.Session() as session:
                session.get(server.url + "/", timeout=40).raise_for_status()
                session.headers["X-CSRF-Token"] = next(
                    unquote(value)
                    for name, value in session.cookies.items()
                    if name.startswith("csrf_token")
                )
                session.post(
                    server.url + "/api/login",
                    json={"user": "relay-test-browser-viewer", "pass": viewer_password},
                    timeout=10,
                ).raise_for_status()
                assert session.get(endpoint, timeout=10).status_code == 403
                session.headers["X-CSRF-Token"] = next(
                    unquote(value)
                    for name, value in session.cookies.items()
                    if name.startswith("csrf_token")
                )
                assert (
                    session.post(endpoint, json={"command": "resync"}, timeout=10).status_code
                    == 403
                )
        for path in server.base.rglob("*.log"):
            content = path.read_bytes()
            assert all(
                secret.encode() not in content
                for secret in (server.key, server.password, viewer_password)
            ), "A disposable credential leaked into a log"
