"""Actual Home Assistant service commands through the installed OctoPrint companion."""

import asyncio
import json
import os
import subprocess
from types import MappingProxyType

import pytest
import yaml

pytest.importorskip("homeassistant")
from homeassistant import loader
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.services import ROOT, IsolatedOctoPrint, broker, free_port, wait_for

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_HA_TESTS") != "1" or not os.environ.get("TEST_OCTOPRINT_PYTHON"),
    reason="Requires disposable HA and a prepared OctoPrint interpreter",
)


def test_i03_actual_ha_to_companion_and_original_to_ha(tmp_path):
    with broker(tmp_path / "broker") as port:
        with IsolatedOctoPrint(
            tmp_path / "octoprint", port, interpreter=os.environ["TEST_OCTOPRINT_PYTHON"]
        ) as server:
            status = wait_for(
                lambda: server.get("/api/plugin/mqttforusbrelaycontrol")
                if server.get("/api/plugin/mqttforusbrelaycontrol")["relays"]
                else None
            )
            identity = status["relays"][0]["id"]
            server.post(
                "/api/settings",
                {
                    "plugins": {
                        "mqttforusbrelaycontrol": {
                            "integration_enabled": True,
                            "device_name": "Synthetic printer",
                            "relays": {
                                identity: {
                                    "enabled": True,
                                    "entity_type": "light",
                                    "display_name": "Synthetic enclosure light",
                                }
                            },
                        }
                    }
                },
            )
            wait_for(lambda: server.get("/api/plugin/mqttforusbrelaycontrol")["ready"])
            asyncio.run(asyncio.wait_for(run_stack(tmp_path / "ha", port, server), timeout=120))


async def run_stack(directory, port, server):
    directory.mkdir()
    frontend = os.environ.get("RUN_HA_BROWSER_TESTS") == "1"
    configuration = {
        "homeassistant": {"name": "Synthetic printer test", "time_zone": "UTC", "country": "DE"},
        "http": {"server_host": "127.0.0.1", "server_port": free_port()},
    }
    if frontend:
        configuration["frontend"] = {}
        storage = directory / ".storage"
        storage.mkdir()
        (storage / "onboarding").write_text(
            json.dumps(
                {
                    "version": 4,
                    "minor_version": 1,
                    "key": "onboarding",
                    "data": {"done": ["user", "core_config", "analytics", "integration"]},
                }
            ),
            encoding="utf-8",
        )
    (directory / "configuration.yaml").write_text(yaml.safe_dump(configuration), encoding="utf-8")
    hass = HomeAssistant(str(directory))
    loader.async_setup(hass)
    assert await async_from_config_dict(configuration, hass) is hass
    try:
        assert await async_setup_component(hass, "mqtt", configuration)
        entry = ConfigEntry(
            domain="mqtt",
            version=2,
            minor_version=1,
            data={"broker": "127.0.0.1", "port": port, "protocol": "5"},
            options={"discovery": True},
            source="user",
            title="Disposable shared broker",
            unique_id=None,
            subentries_data=[],
            discovery_keys=MappingProxyType({}),
        )
        await hass.config_entries.async_add(entry)
        await hass.async_start()

        async def until(predicate):
            deadline = asyncio.get_running_loop().time() + 20
            while asyncio.get_running_loop().time() < deadline:
                value = predicate()
                if value:
                    return value
                await asyncio.sleep(0.1)
            raise AssertionError("The isolated end-to-end state did not converge")

        entity = await until(
            lambda: next(
                (
                    state
                    for state in hass.states.async_all("light")
                    if state.attributes.get("friendly_name", "").endswith(
                        "Synthetic enclosure light"
                    )
                ),
                None,
            )
        )
        await until(lambda: hass.states.get(entity.entity_id).state == "off")
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": entity.entity_id}, blocking=True
        )
        await until(lambda: hass.states.get(entity.entity_id).state == "on")
        status = await asyncio.to_thread(server.get, "/api/plugin/mqttforusbrelaycontrol")
        assert status["relays"][0]["snapshot"]["actual"] is True
        assert await asyncio.to_thread(server.get, "/api/plugin/usbrelaycontrol") == ["on"]
        if frontend:
            from homeassistant.helpers import device_registry

            device = next(
                device
                for device in device_registry.async_get(hass).devices
                if any(
                    identifier.startswith("mqttforusbrelaycontrol_")
                    for _, identifier in device.identifiers
                )
            )
            user = await hass.auth.async_create_user(
                "Disposable test admin", group_ids=[GROUP_ID_ADMIN], local_only=True
            )
            refresh = await hass.auth.async_create_refresh_token(
                user, client_id=f"http://127.0.0.1:{configuration['http']['server_port']}/"
            )
            token = hass.auth.async_create_access_token(refresh)
            environment = dict(
                os.environ,
                TEST_HA_URL=f"http://127.0.0.1:{configuration['http']['server_port']}",
                TEST_HA_TOKEN=token,
                TEST_HA_DEVICE_ID=device.id,
            )
            result = await asyncio.to_thread(
                subprocess.run,
                ["node", "tests/ha/screenshots.ts"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                timeout=75,
            )
            assert result.returncode == 0, (
                "The isolated HA browser capture failed; no credentials are printed"
            )
        await asyncio.to_thread(
            server.post, "/api/plugin/usbrelaycontrol", {"command": "turnUSBRelayOff", "id": 0}
        )
        await until(lambda: hass.states.get(entity.entity_id).state == "off")
        status = await asyncio.to_thread(server.get, "/api/plugin/mqttforusbrelaycontrol")
        assert status["relays"][0]["snapshot"]["actual"] is False
    finally:
        await hass.async_stop()
