"""Durable optional identity fallback uses only validated companion-owned data."""

import json
from unittest.mock import Mock

import pytest

from octoprint_mqttforusbrelaycontrol.device_identity import DeviceIdentityCache


def test_identity_cache_reloads_and_retries_failed_atomic_replacement(tmp_path, monkeypatch):
    cache = DeviceIdentityCache(tmp_path)
    old = {"node_id": "ABC123", "node_name": "Printer"}
    new = {"node_id": "New-ID", "node_name": None}
    assert cache.remember(old)
    with monkeypatch.context() as context:
        context.setattr("os.replace", Mock(side_effect=OSError("Synthetic disk failure")))
        assert not cache.remember(new)
        assert not cache.remember(new)
    assert cache.value == new
    assert DeviceIdentityCache(tmp_path).value == old
    assert cache.remember(old)
    assert cache.value == old
    assert cache.remember(new)
    assert DeviceIdentityCache(tmp_path).value == new
    assert not list(tmp_path.glob(".device-identity-*"))


@pytest.mark.parametrize(
    "data",
    [
        "invalid json",
        "[]",
        "{}",
        json.dumps({"schema": 1, "device": {"node_id": "\u0000", "node_name": "Printer"}}),
    ],
)
def test_corrupt_identity_cache_is_ignored(tmp_path, data):
    (tmp_path / "device-identity.json").write_text(data, encoding="utf-8")
    assert DeviceIdentityCache(tmp_path).value is None
