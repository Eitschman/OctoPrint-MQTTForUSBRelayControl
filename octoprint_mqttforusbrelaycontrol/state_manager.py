"""Bounded command processing and coalesced current-state delivery."""

import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from time import monotonic, time
from typing import Any

from .command_settings import validate_command_timing
from .constants import COMMAND_MAX_AGE_SECONDS, COMMAND_MIN_INTERVAL_SECONDS, COMMAND_QUEUE_LIMIT


@dataclass(frozen=True)
class Command:
    relay_id: str
    generation: int
    epoch: int
    target: bool
    retained: bool
    received_at: float = field(default_factory=monotonic)


class StateManager:
    def __init__(
        self,
        execute,
        publish,
        reconcile,
        diagnostic,
        limit=COMMAND_QUEUE_LIMIT,
        clock=monotonic,
        changed=None,
    ):
        self.execute, self.publish, self.reconcile = execute, publish, reconcile
        self.diagnostic = diagnostic
        self.limit = limit
        self.clock = clock
        self.changed = changed or (lambda: None)
        self.max_command_age = COMMAND_MAX_AGE_SECONDS
        self.min_command_interval = COMMAND_MIN_INTERVAL_SECONDS
        self.last_completed: dict[str, float] = {}
        self.cursor = 0
        self.condition = threading.Condition()
        self.commands: deque[Command] = deque()
        self.pending: dict[str, dict[str, Any]] = {}
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.controls: dict[str, bool] = {}
        self.epoch = 0
        self.revision = 0
        self.running = False
        self.thread = None
        self.busy = False
        self.rejected = 0
        self.expired = 0
        self.overflows = 0
        self.active_kind: str | None = None
        self.active_started: float | None = None
        self.last_duration: float | None = None

    def configure_commands(self, max_age, min_interval):
        max_age = validate_command_timing("command_max_age", max_age)
        min_interval = validate_command_timing("command_min_interval", min_interval)
        with self.condition:
            self.max_command_age = max_age
            self.min_command_interval = min_interval
            self.condition.notify_all()

    def command_permitted(self, command):
        """Recheck expiry after waiting for the original hardware lock as well."""
        with self.condition:
            if command.epoch != self.epoch or command.retained is not False:
                return False
            if self.clock() - command.received_at >= self.max_command_age:
                self.expired += 1
                self.rejected += 1
                return False
            return True

    def current_epoch(self):
        with self.condition:
            return self.epoch

    def invalidate(self):
        with self.condition:
            self.epoch += 1
            self.commands.clear()
            self.pending.clear()
            self.snapshots.clear()
            self.condition.notify_all()
            return self.epoch

    def observe(self, observation):
        with self.condition:
            previous = self.snapshots.get(observation.relay_id)
            if observation.epoch != self.epoch or (
                previous and previous["sequence"] >= observation.sequence
            ):
                return
            self.revision += 1
            snapshot = dict(
                asdict(observation),
                outcome=observation.outcome,
                revision=self.revision,
                timestamp=time(),
            )
            self.snapshots[observation.relay_id] = snapshot
            self.pending[observation.relay_id] = snapshot
            self.condition.notify_all()

    def enqueue(self, command):
        with self.condition:
            if (
                not self.running
                or command.retained is not False
                or command.epoch != self.epoch
                or len(self.commands) >= self.limit
            ):
                self.rejected += 1
                if len(self.commands) >= self.limit:
                    self.overflows += 1
                return False
            if not self.command_permitted(command):
                return False
            self.commands.append(command)
            self.condition.notify_all()
            return True

    def request(self, reason="sync"):
        with self.condition:
            if self.running:
                self.controls[reason] = True
                self.condition.notify_all()

    def start(self):
        with self.condition:
            if self.running:
                return
            self.running = True
            self.thread = threading.Thread(target=self._run, name="mqtt-relay-worker", daemon=True)
            self.thread.start()

    def _select_work(self):
        """Called under the condition: rotate controls, commands and publications."""
        previous_count = len(self.commands)
        self.commands = deque(
            command for command in self.commands if self.command_permitted(command)
        )
        now = self.clock()
        self.last_completed = {
            identity: completed
            for identity, completed in self.last_completed.items()
            if completed + self.min_command_interval > now
        }
        command_index = next(
            (
                index
                for index, command in enumerate(self.commands)
                if command.relay_id not in self.last_completed
            ),
            None,
        )
        kinds = ("reconcile", "command", "publish")
        available = (bool(self.controls), command_index is not None, bool(self.pending))
        for offset in range(3):
            index = (self.cursor + offset) % 3
            if not available[index]:
                continue
            self.cursor = (index + 1) % 3
            kind = kinds[index]
            if kind == "reconcile":
                reasons = tuple(self.controls)
                self.controls.clear()
                return (kind, reasons), None
            if kind == "command":
                if command_index is None:
                    raise RuntimeError("Selected command is unavailable")
                command = self.commands[command_index]
                del self.commands[command_index]
                return (kind, command), None
            identity = next(iter(self.pending))
            return (kind, self.pending.pop(identity)), None
        if previous_count != len(self.commands):
            return ("expire", None), None
        # This is a deadline wait for queued commands, not a hardware poll.
        delay = min(
            (
                min(
                    self.last_completed[command.relay_id] + self.min_command_interval,
                    command.received_at + self.max_command_age,
                )
                - now
                for command in self.commands
            ),
            default=None,
        )
        return None, delay

    def status(self):
        with self.condition:
            now = self.clock()
            return {
                "queued": len(self.commands),
                "expired": self.expired,
                "overflows": self.overflows,
                "rejected": self.rejected,
                "oldest_age": max(
                    (now - command.received_at for command in self.commands), default=0
                ),
                "active": self.active_kind,
                "elapsed": now - self.active_started if self.active_started is not None else None,
                "last_duration": self.last_duration,
            }

    def _run(self):
        while True:
            with self.condition:
                while self.running:
                    work, delay = self._select_work()
                    if work is not None:
                        break
                    self.condition.wait(delay)
                if not self.running:
                    break
                if work is None:
                    raise RuntimeError("Selected worker operation is unavailable")
                self.busy = True
                kind, value = work
                started = self.clock()
                self.active_kind, self.active_started = kind, started
            try:
                if kind == "reconcile":
                    self.reconcile(value)
                elif kind == "command":
                    if not isinstance(value, Command):
                        raise TypeError("Worker command has an invalid type")
                    if self.command_permitted(value):
                        self.execute(value)
                elif kind == "publish":
                    if not isinstance(value, dict):
                        raise TypeError("Worker publication has an invalid type")
                    if value["epoch"] == self.current_epoch():
                        self.publish(value)
            except Exception as error:
                try:
                    self.diagnostic(f"Worker operation failed: {type(error).__name__}")
                except Exception as callback_error:
                    logging.getLogger(__name__).warning(
                        "Worker diagnostic callback failed: %s", type(callback_error).__name__
                    )
            finally:
                with self.condition:
                    if kind == "command" and isinstance(value, Command):
                        self.last_completed[value.relay_id] = self.clock()
                    self.last_duration = self.clock() - started
                    self.active_kind = self.active_started = None
                    self.busy = False
                    self.condition.notify_all()
                try:
                    self.changed()
                except Exception as error:
                    logging.getLogger(__name__).warning(
                        "Worker notification callback failed: %s", type(error).__name__
                    )

    def wait_idle(self, timeout=5):
        with self.condition:
            return self.condition.wait_for(
                lambda: not (self.busy or self.controls or self.commands or self.pending), timeout
            )

    def stop(self, timeout=2):
        self.invalidate()
        with self.condition:
            self.running = False
            self.controls.clear()
            self.condition.notify_all()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout)
            if self.thread.is_alive():
                self.diagnostic("Worker is blocked in an upstream operation; restart required")
                return False
        return True
