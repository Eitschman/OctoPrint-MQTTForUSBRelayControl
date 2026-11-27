"""Reversible instance wrappers; all original hardware operations share one lock."""

import functools
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass

from .operations import OperationMonitor


@dataclass(frozen=True)
class Observation:
    relay_id: str
    generation: int
    epoch: int
    target: bool | None
    actual: bool | None
    write_error: str | None = None
    read_error: str | None = None
    sequence: int = 0

    @property
    def outcome(self):
        if self.read_error:
            return "read_failed"
        if self.write_error:
            return "write_failed"
        if self.target is not None and self.actual != self.target:
            return "mismatch"
        return "confirmed"


class InstanceAdapter:
    def __init__(
        self, original, registry, sink, invalidate, epoch, options, diagnostic, changed=None
    ):
        self.original, self.registry = original, registry
        self.sink, self.invalidate, self.epoch = sink, invalidate, epoch
        self.options, self.diagnostic = options, diagnostic
        self.changed = changed or (lambda: None)
        self.reconfiguring = threading.Event()
        self.configuration_guard = threading.Lock()
        self.reconfiguration_count = 0
        self.lock = threading.RLock()
        self.local = threading.local()
        self.manifest = []
        self.active = False
        self.sequence = 0
        self.teardown_complete = True
        self.operations = OperationMonitor(diagnostic)

    @contextmanager
    def transaction(self):
        outer = getattr(self.local, "depth", 0) == 0
        observations = []
        try:
            with self.lock:
                if outer:
                    self.local.observations = {}
                    self.local.epoch = self.epoch()
                self.local.depth = getattr(self.local, "depth", 0) + 1
                try:
                    yield
                finally:
                    self.local.depth -= 1
                    observations = list(self.local.observations.values()) if outer else []
        finally:
            for observation in observations:
                try:
                    self.sink(observation)
                except Exception as error:
                    self._diagnose("State observer failed", error)

    def _diagnose(self, message, error):
        try:
            self.diagnostic(f"{message}: {type(error).__name__}")
        except Exception as callback_error:
            logging.getLogger(__name__).warning(
                "Diagnostic callback failed: %s", type(callback_error).__name__
            )

    def _wrap(self, obj, name, handler):
        previous = getattr(obj, name)
        had_own = name in vars(obj)
        own_value = vars(obj).get(name)
        token = {"active": True}

        @functools.wraps(previous)
        def wrapper(*args, **kwargs):
            if not self.active or not token["active"]:
                return previous(*args, **kwargs)
            return handler(previous, *args, **kwargs)

        setattr(obj, name, wrapper)
        self.manifest.append((obj, name, wrapper, had_own, own_value, previous, token))

    def install(self):
        with self.lock:
            if self.active:
                return
            self.active = True
            for name in ("on_api_command", "on_api_get"):
                self._wrap(self.original, name, self._guarded)
            for name in ("on_settings_save", "on_after_startup"):
                self._wrap(self.original, name, self._reconfigure)
            self.registry.rebuild(self.original, self.options())
            self._bind_relays()

    def _guarded(self, previous, *args, **kwargs):
        with self.transaction():
            return previous(*args, **kwargs)

    def _reconfigure(self, previous, *args, **kwargs):
        with self.configuration_guard:
            self.reconfiguration_count += 1
            self.reconfiguring.set()
        self.invalidate()
        try:
            with self.transaction():
                try:
                    with self.operations.track("configuration"):
                        return previous(*args, **kwargs)
                finally:
                    try:
                        self.registry.rebuild(self.original, self.options())
                        self._bind_relays()
                        self._read_entries(list(self.registry.entries.values()))
                    except Exception as error:
                        self.registry.entries = {}
                        self._bind_relays()
                        self._diagnose("Original relay rebinding failed", error)
        finally:
            with self.configuration_guard:
                self.reconfiguration_count -= 1
                if not self.reconfiguration_count:
                    self.reconfiguring.clear()
            try:
                self.changed()
            except Exception as error:
                self._diagnose("Reconfiguration notification failed", error)

    def _bind_relays(self):
        current = {id(entry.relay): entry.relay for entry in self.registry.entries.values()}
        obsolete = [
            binding
            for binding in self.manifest
            if binding[1] == "state" and id(binding[0]) not in current
        ]
        self._restore(obsolete)
        self.manifest = [
            binding
            for binding in self.manifest
            if binding[1] != "state" or id(binding[0]) in current
        ]
        for relay in current.values():
            if any(obj is relay and name == "state" for obj, name, *_ in self.manifest):
                continue
            self._wrap(
                relay,
                "state",
                lambda previous, *args, _relay=relay, **kwargs: self._state(
                    _relay, previous, *args, **kwargs
                ),
            )

    def _raw(self, relay):
        for obj, name, wrapper, _, _, previous, _ in reversed(self.manifest):
            if obj is relay and name == "state":
                if getattr(obj, name) is not wrapper:
                    raise RuntimeError("Relay wrapper ownership changed; restart required")
                return previous
        raise RuntimeError("Relay object is no longer bound")

    def _record(self, entry, actual, target=None, write_error=None, read_error=None):
        self.sequence += 1
        observation = Observation(
            entry.id,
            entry.generation,
            self.local.epoch,
            target,
            actual,
            write_error,
            read_error,
            self.sequence,
        )
        self.local.observations[entry.id] = observation
        return observation

    def _read_entry(self, entry, target=None, write_error=None):
        try:
            with self.operations.track("read"):
                value = self._raw(entry.relay)(entry.channel)
            if type(value) is not bool:
                raise ValueError("Unexpected physical relay state")
            return self._record(entry, entry.logical(value), target, write_error)
        except Exception as error:
            return self._record(entry, None, target, write_error, type(error).__name__)

    def _read_entries(self, entries):
        return [self._read_entry(entry) for entry in entries]

    def _state(self, relay_object, previous, *args, **kwargs):
        with self.transaction():
            channel = kwargs.get("relay", args[0] if args else None)
            on = kwargs.get("on", args[1] if len(args) > 1 else None)
            entries = self.registry.for_object(relay_object, channel)
            if on is None:
                try:
                    with self.operations.track("read"):
                        result = previous(*args, **kwargs)
                except Exception as error:
                    for entry in entries:
                        self._record(entry, None, read_error=type(error).__name__)
                    raise
                for entry in entries:
                    try:
                        value = result[entry.channel - 1] if channel == 0 else result
                        if type(value) is not bool:
                            raise ValueError("Unexpected physical relay state")
                        self._record(entry, entry.logical(value))
                    except Exception as error:
                        self._record(entry, None, read_error=type(error).__name__)
                return result
            try:
                with self.operations.track("write"):
                    result = previous(*args, **kwargs)
            except Exception as error:
                for entry in entries:
                    self._read_entry(entry, entry.logical(bool(on)), type(error).__name__)
                raise
            for entry in entries:
                self._read_entry(entry, entry.logical(bool(on)))
            return result

    def read_all(self):
        with self.transaction():
            return self._read_entries(list(self.registry.entries.values()))

    def write_verified(self, identity, generation, target, allowed):
        with self.transaction():
            entry = self.registry.current(identity, generation)
            if entry is None or not entry.enabled or self.reconfiguring.is_set() or not allowed():
                return None
            error_name = None
            try:
                with self.operations.track("write"):
                    self._raw(entry.relay)(entry.channel, on=entry.physical(target))
            except Exception as error:
                error_name = type(error).__name__
            return self._read_entry(entry, target, error_name)

    def refresh(self):
        with self.transaction():
            self.registry.rebuild(self.original, self.options())
            self._bind_relays()
            return self._read_entries(list(self.registry.entries.values()))

    def uninstall(self, timeout=2):
        self.active = False
        self.invalidate()
        if not self.lock.acquire(timeout=timeout):
            self.teardown_complete = False
            self._diagnose(
                "Hardware access is still running; wrappers inactive, restart required",
                TimeoutError(),
            )
            return False
        try:
            self._restore(self.manifest)
            self.manifest.clear()
            return self.teardown_complete
        finally:
            self.lock.release()

    def _restore(self, bindings):
        for obj, name, wrapper, had_own, own_value, _, token in reversed(bindings):
            token["active"] = False
            if getattr(obj, name, None) is not wrapper:
                self.teardown_complete = False
                self._diagnose("Wrapper ownership changed; restart required", RuntimeError())
                continue
            if had_own:
                setattr(obj, name, own_value)
            else:
                delattr(obj, name)
