"""Event-driven binding, connection gates, reconciliation and teardown."""

import copy
import json
import logging
import threading
from dataclasses import fields
from pathlib import Path
from time import time
from uuid import UUID, uuid4

from ._version import __version__
from .adapter import InstanceAdapter
from .compatibility import check_compatibility, check_mqtt_compatibility
from .constants import DEFAULTS, IDENTIFIER
from .device_identity import DeviceIdentityCache
from .discovery import (
    DiscoveryLedger,
    discovery_configuration,
    discovery_device,
    valid_device_identifier,
)
from .mqtt_integration import (
    MQTTIntegration,
    command_payload,
    concrete_topic,
    mqtt_requirements,
    relay_topics,
    topic_prefix,
)
from .relay_registry import RelayRegistry
from .state_manager import Command, StateManager


class RelayRuntime:
    def __init__(self, manager, settings, data_folder, logger, notify):
        self.manager, self.settings = manager, settings
        self.data_folder, self.logger, self.notify = Path(data_folder), logger, notify
        self.guard = threading.RLock()
        self.connected = None
        self.connection_observed = False
        self.ready = False
        self.closed = False
        self.registered = False
        self.last_error = None
        self.error_time = None
        self.adapter = None
        self.registry = None
        self.transport = None
        self.ledger = None
        self.configurations = {}
        self.topics = {}
        self.lwt_topic = None
        self.fingerprint = None
        self.device = {}
        self.device_source = "separate"
        self.device_cache = DeviceIdentityCache(self.data_folder)
        self.device_identity_cached = False
        self.device_warning = None
        self.restart_required = False
        self.frontend_compatible = None
        self.last_sync = None
        self.versions = {}
        self.suspended = set()
        self.retry_count = 0
        self.pending_clone = False
        self.timers = []
        self.worker = StateManager(
            self._execute,
            self._publish_snapshot,
            self._reconcile,
            self.diagnostic,
            changed=self._notify,
        )

    def configuration(self):
        return {key: copy.deepcopy(self.settings.get([key])) for key in DEFAULTS}

    def diagnostic(self, message):
        with self.guard:
            changed = self.last_error != message
            self.last_error, self.error_time = message, time()
        if changed:
            self.logger.warning(message)
        self._notify()

    def _notify(self):
        try:
            self.notify(self.status())
        except Exception:
            self.logger.debug("Plugin status notification failed", exc_info=False)

    def register_receiver(self):
        with self.guard:
            if self.closed:
                return
            if not self.registered:
                self.manager.register_message_receiver(self.on_plugin_message)
                self.registered = True

    def start(self):
        if self.closed:
            return
        self.register_receiver()
        self.worker.start()
        self.worker.request("start")

    def on_plugin_message(self, sender, payload, permissions=None):
        if (
            sender != "mqtt"
            or not isinstance(payload, dict)
            or type(payload.get("connected")) is not bool
        ):
            return
        with self.guard:
            if self.closed:
                return
            self.connected = payload["connected"]
            self.connection_observed = True
            self.ready = False
            self.worker.invalidate()
        self.worker.request("connection")
        self.logger.info("MQTT connection state changed: %s", self.connected)
        self._notify()

    def invalidate(self):
        with self.guard:
            self.ready = False
            self.worker.invalidate()

    def settings_updated(self):
        self.worker.request("settings")

    def _retry(self):
        if self.retry_count >= 3 or self.closed:
            return
        delay = (0.5, 1.0, 2.0)[self.retry_count]
        self.retry_count += 1
        timer = threading.Timer(delay, lambda: self.worker.request("retry"))
        timer.daemon = True
        self.timers.append(timer)
        timer.start()

    def _bootstrap(self, topic, payload, **metadata):
        if metadata.get("retained") is not True or payload not in (
            b"connected",
            b"disconnected",
            "connected",
            "disconnected",
        ):
            return
        with self.guard:
            if self.connection_observed or self.connected is not None or self.closed:
                return
            self.connected = payload in (b"connected", "connected")
            self.worker.invalidate()
        self.worker.request("bootstrap")

    def _birth(self, topic, payload, **metadata):
        expected = self.configuration()["ha_birth_payload"]
        if payload in (expected, expected.encode("utf-8")):
            self.worker.request("birth")

    def _command_callback(self, entry):
        def callback(topic, payload, **metadata):
            if metadata.get("retained") is not False:
                return
            target = command_payload(payload)
            with self.guard:
                if target is None or not self.ready or self.closed:
                    return
                epoch = self.worker.current_epoch()
            self.worker.enqueue(Command(entry.id, entry.generation, epoch, target, False))

        return callback

    def _allowed(self, epoch):
        with self.guard:
            return (
                self.ready
                and self.connected is True
                and not self.closed
                and not self.pending_clone
                and epoch == self.worker.current_epoch()
            )

    def _can_submit(self, epoch, identity):
        with self.guard:
            return (
                self.connected is True
                and not self.closed
                and not self.pending_clone
                and epoch == self.worker.current_epoch()
                and self.settings.get(["instance_uuid"]) == identity
            )

    def _execute(self, command):
        adapter = self.adapter
        if adapter and command.retained is False:
            adapter.write_verified(
                command.relay_id,
                command.generation,
                command.target,
                lambda: self._allowed(command.epoch) and self.worker.command_permitted(command),
            )

    def _observe(self, observation):
        registry = self.registry
        if registry and registry.current(observation.relay_id, observation.generation):
            self.worker.observe(observation)

    def _unbind(self):
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.adapter:
            if not self.adapter.uninstall():
                self.restart_required = True
            self.adapter = None
        self.registry = None
        self.topics = {}
        self.fingerprint = None

    def _publish_unavailable(self):
        ledger = self.ledger
        epoch = self.worker.current_epoch()
        if not ledger or not self._can_submit(epoch, ledger.instance_uuid):
            return
        transport = self.transport
        temporary = transport is None
        if temporary:
            try:
                info = self._dependency("mqtt")
                helpers = (
                    self.manager.get_helpers(
                        "mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe"
                    )
                    or {}
                )
                if not check_mqtt_compatibility(info.version, helpers).compatible:
                    return
                transport = MQTTIntegration(helpers, self.diagnostic)
            except Exception as error:
                self.logger.debug("Availability transport unavailable: %s", type(error).__name__)
                return
        if transport is None:
            self.logger.warning("Availability transport is unavailable")
            return
        try:
            for topic in sorted(ledger.availability | ledger.retired_availability):
                if not self._can_submit(epoch, ledger.instance_uuid):
                    return
                transport.publish(topic, "offline")
        finally:
            if temporary:
                transport.close()

    def _dependency(self, key):
        if key in self.suspended:
            raise ValueError(f"Required plugin is disabled or pending restart: {key}")
        info = self.manager.get_plugin_info(key, require_enabled=True)
        if not info or not info.implementation:
            raise ValueError(f"Required plugin is unavailable: {key}")
        return info

    def _bind(self, config):
        if self.restart_required:
            raise ValueError("Previous hardware binding could not be restored; restart required")
        usb, mqtt = self._dependency("usbrelaycontrol"), self._dependency("mqtt")
        self.versions = {"usbrelaycontrol": usb.version, "mqtt": mqtt.version}
        helpers = (
            self.manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
            or {}
        )
        result = check_compatibility(usb.implementation, usb.version, mqtt.version, helpers)
        if not result.compatible:
            raise ValueError("; ".join(result.errors))
        identity = str(UUID(config["instance_uuid"]))
        self.ledger = DiscoveryLedger(self.data_folder, identity)
        self.registry = RelayRegistry(identity)
        self.transport = MQTTIntegration(helpers, self.diagnostic)
        self.adapter = InstanceAdapter(
            usb.implementation,
            self.registry,
            self._observe,
            self.invalidate,
            self.worker.current_epoch,
            lambda: self.configuration()["relays"] or {},
            self.diagnostic,
            changed=lambda: self.worker.request("original_changed"),
        )
        self.adapter.install()
        return mqtt.implementation

    def _reconcile(self, reasons):
        if self.closed:
            return
        if self.adapter and self.adapter.reconfiguring.is_set():
            return
        if self.pending_clone:
            self._unbind()
            self.ledger = None
            self.pending_clone = False
        elif "dependency" in reasons:
            # Plugin reactivation can replace both plugin instances and helper objects.
            self._publish_unavailable()
            self._unbind()
        config = self.configuration()
        self.logger.setLevel(logging.DEBUG if config["debug_logging"] else logging.INFO)
        mqtt_info = self.manager.get_plugin_info("mqtt", require_enabled=True)
        mqtt_publish = (
            [
                mqtt_info.implementation._settings.get(["publish", key])
                for key in ("baseTopic", "lwTopic", "lwActive")
            ]
            if mqtt_info and mqtt_info.implementation
            else None
        )
        existing_device = self._existing_device(config)
        fingerprint = json.dumps([config, mqtt_publish, existing_device], sort_keys=True)
        if reasons == ("settings",) and fingerprint == self.fingerprint and self.ready:
            self._notify()
            return
        with self.guard:
            self.ready = False
        try:
            self.worker.configure_commands(
                config["command_max_age"], config["command_min_interval"]
            )
            if self.adapter is None:
                mqtt = self._bind(config)
            else:
                mqtt = self._dependency("mqtt").implementation
                self._dependency("usbrelaycontrol")
            if (
                self.adapter is None
                or self.registry is None
                or self.transport is None
                or self.ledger is None
            ):
                raise ValueError("Companion dependencies are not bound")
            # LWT errors gate the companion but never change another plugin's settings.
            prefix, lwt = mqtt_requirements(mqtt._settings)
            device, device_source = discovery_device(config, prefix, existing_device)
            prefix = topic_prefix(config["mqtt_prefix"] or prefix)
            birth = concrete_topic(config["ha_birth_topic"])
            topic_prefix(config["discovery_prefix"])
            if birth == lwt:
                raise ValueError("Home Assistant birth and MQTT Last Will topics must differ")
            self.lwt_topic = lwt
            if fingerprint != self.fingerprint or "original_changed" in reasons:
                self.worker.invalidate()
                self.adapter.refresh()
            self.fingerprint = fingerprint
            entries = list(self.registry.entries.values())
            topics = {
                entry.id: relay_topics(prefix, self.registry.instance_uuid, entry)
                for entry in entries
            }
            concrete = [value for values in topics.values() for value in values.values()]
            if len(set(concrete + [birth, lwt])) != len(concrete) + 2:
                raise ValueError("MQTT command, state, availability and status topics must differ")
            self.topics = topics
            desired_subscriptions = {lwt}
            self.transport.subscribe(lwt, self._bootstrap)
            enabled = config["integration_enabled"] is True
            configurations = {}
            availability = set()
            if enabled:
                desired_subscriptions.add(birth)
                self.transport.subscribe(birth, self._birth)
                for entry in entries:
                    if not entry.enabled:
                        continue
                    topic = topics[entry.id]["set"]
                    desired_subscriptions.add(topic)
                    # A rebuilt registry changes the captured generation; replace this exact subscription.
                    self.transport.unsubscribe(topic)
                    self.transport.subscribe(topic, self._command_callback(entry))
                    availability.add(topics[entry.id]["availability"])
                    if config["discovery_enabled"]:
                        discovery_topic, payload = discovery_configuration(
                            entry,
                            self.registry.instance_uuid,
                            config["discovery_prefix"],
                            topics[entry.id],
                            lwt,
                            config["device_name"],
                            device=device,
                        )
                        if discovery_topic in concrete or discovery_topic in (birth, lwt):
                            raise ValueError("Discovery and runtime topics must differ")
                        configurations[discovery_topic] = payload
            self.transport.retain_subscriptions(desired_subscriptions)
            self.ledger.update(configurations, availability)
            with self.guard:
                self.device, self.device_source = device, device_source
            self.configurations = configurations
            publish_epoch = self.worker.current_epoch()
            publish_identity = self.registry.instance_uuid
            self.ledger.submit_retirements(
                self.transport, lambda: self._can_submit(publish_epoch, publish_identity)
            )
            for topic, payload in configurations.items():
                if self._can_submit(publish_epoch, publish_identity):
                    self.transport.publish(topic, payload)
            self.adapter.read_all()
            self.last_sync = time()
            self.logger.debug("Reconciled %d relay channels", len(entries))
            with self.guard:
                self.ready = (
                    enabled
                    and self.connected is True
                    and not self.closed
                    and not self.pending_clone
                    and publish_epoch == self.worker.current_epoch()
                    and config["instance_uuid"] == self.settings.get(["instance_uuid"])
                    and not self.adapter.reconfiguring.is_set()
                )
                if self.registry.errors:
                    self.last_error = "; ".join(self.registry.errors)
                else:
                    self.last_error = None
            if not entries:
                self._retry()
        except Exception as error:
            self.worker.invalidate()
            if self.transport:
                self.transport.retain_subscriptions(set())
            self._publish_unavailable()
            self.diagnostic(
                str(error)
                if isinstance(error, ValueError)
                else f"Dependency reconciliation failed: {type(error).__name__}"
            )
            self._retry()
        self._notify()

    def _publish_snapshot(self, snapshot):
        identity = snapshot["relay_id"]
        if not self.registry or not self.registry.current(identity, snapshot["generation"]):
            return
        entry = self.registry.entries[identity]
        if snapshot["outcome"] != "confirmed":
            self.diagnostic(f"Relay state verification failed: {snapshot['outcome']}")
        # The frontend receives local observations even while MQTT integration is disabled.
        self._notify()
        epoch = snapshot["epoch"]
        if (
            not entry.enabled
            or not self._allowed(epoch)
            or identity not in self.topics
            or self.transport is None
        ):
            return
        topics = self.topics[identity]
        actual = snapshot["actual"]
        if actual is not None and self._allowed(epoch):
            self.transport.publish(topics["state"], "ON" if actual else "OFF")
        if self._allowed(epoch):
            self.transport.publish(
                topics["availability"],
                "online"
                if actual is not None and snapshot["outcome"] == "confirmed"
                else "offline",
            )

    def _existing_device(self, config):
        """Read only the optional discovery plugin's published identity settings."""
        self.device_identity_cached = False
        self.device_warning = None
        if (
            not config["use_octoprint_device"]
            or config["device_identifier"]
            or "homeassistant" in self.suspended
        ):
            return None
        try:
            info = self.manager.get_plugin_info("homeassistant", require_enabled=True)
            if not info or not info.implementation:
                return None
            settings = info.implementation._settings
            identifier = settings.get(["node_id"])
            if not valid_device_identifier(identifier):
                return self._cached_device()
            name = settings.get(["node_name"])
            device = {
                "node_id": identifier,
                "node_name": name if valid_device_identifier(name) else None,
            }
        except Exception as error:
            self.logger.debug("Optional device identity unavailable: %s", type(error).__name__)
            return self._cached_device()
        if not self.device_cache.remember(device):
            self.device_warning = "cache_write_failed"
        return device

    def _cached_device(self):
        self.device_identity_cached = self.device_cache.value is not None
        self.device_warning = "cached" if self.device_identity_cached else "unavailable"
        return copy.deepcopy(self.device_cache.value)

    def on_event(self, event, payload):
        if event == "SettingsUpdated":
            self.settings_updated()
            return
        key = payload.get("id") if isinstance(payload, dict) else None
        if key not in (IDENTIFIER, "usbrelaycontrol", "mqtt", "homeassistant"):
            return
        if key == "homeassistant":
            if event in (
                "plugin_pluginmanager_disable_plugin",
                "plugin_pluginmanager_uninstall_plugin",
            ):
                self.suspended.add(key)
            elif event == "plugin_pluginmanager_enable_plugin":
                self.suspended.discard(key)
            else:
                return
            self.worker.request("settings")
            return
        if event in (
            "plugin_pluginmanager_disable_plugin",
            "plugin_pluginmanager_uninstall_plugin",
        ):
            if key == IDENTIFIER:
                self.stop()
                return
            self.suspended.add(key)
            self.invalidate()
            self.worker.request("dependency")
        elif event == "plugin_pluginmanager_enable_plugin":
            self.suspended.discard(key)
            self.invalidate()
            self.worker.request("dependency")

    def clone_identity(self, confirmed):
        with self.guard:
            if not confirmed or self.connected is not False or self.ready:
                raise ValueError(
                    "A confirmed offline connection is required before changing clone identity"
                )
            self.worker.invalidate()
            self.pending_clone = True
            identity = str(uuid4())
            old = self.settings.get(["instance_uuid"])
            self.settings.set(["instance_uuid"], identity)
            try:
                self.settings.save(force=True)
            except Exception:
                self.settings.set(["instance_uuid"], old)
                self.pending_clone = False
                raise
        self.worker.request("clone")
        return identity

    def status(self):
        with self.guard, self.worker.condition:
            rows = []
            if self.registry:
                for entry in self.registry.entries.values():
                    row = {
                        field.name: getattr(entry, field.name)
                        for field in fields(entry)
                        if field.name != "relay"
                    }
                    row["snapshot"] = copy.deepcopy(self.worker.snapshots.get(entry.id))
                    rows.append(row)
            return {
                "schema": 1,
                "epoch": self.worker.epoch,
                "revision": self.worker.revision,
                "connected": self.connected,
                "ready": self.ready,
                "relays": rows,
                "last_error": self.last_error,
                "error_time": self.error_time,
                "versions": dict(self.versions, **{IDENTIFIER: __version__}),
                "last_sync": self.last_sync,
                "enabled_count": sum(row["enabled"] for row in rows),
                "frontend_compatible": self.frontend_compatible,
                "discovery_count": len(self.configurations),
                "device_identifier": next(iter(self.device.get("identifiers", [])), None),
                "device_source": self.device_source,
                "device_identity_cached": self.device_identity_cached,
                "device_warning": self.device_warning,
                "worker": self.worker.status(),
                "hardware": self.adapter.operations.status() if self.adapter else {},
                "restart_required": self.restart_required,
                "pending_deletions": len(self.ledger.tombstones) if self.ledger else 0,
                "publish_submitted": self.transport.submitted if self.transport else 0,
                "publish_failed": self.transport.failed if self.transport else 0,
                "rejected_commands": self.worker.rejected,
            }

    def stop(self):
        with self.guard:
            if self.closed:
                return
            self.closed, self.ready = True, False
            self.worker.invalidate()
        for timer in self.timers:
            timer.cancel()
        if self.registered:
            self.manager.unregister_message_receiver(self.on_plugin_message)
            self.registered = False
        joined = self.worker.stop()
        if not joined:
            # Do not wait indefinitely for the same hardware lock during shutdown.
            if self.adapter:
                self.adapter.active = False
            if self.transport:
                self.transport.close()
            return
        if (
            self.transport
            and self.connected is True
            and self.ledger
            and self.settings.get(["instance_uuid"]) == self.ledger.instance_uuid
        ):
            for topic in self.ledger.availability:
                self.transport.publish(topic, "offline")
        self._unbind()
