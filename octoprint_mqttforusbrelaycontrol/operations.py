"""One-shot diagnostics for serialized upstream operations; never cancel hardware."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic

from .constants import HARDWARE_WARNING_SECONDS


@dataclass
class Operation:
    kind: str
    started: float
    slow: bool = False


class OperationMonitor:
    def __init__(self, diagnostic, threshold=HARDWARE_WARNING_SECONDS, clock=monotonic):
        self.diagnostic, self.threshold, self.clock = diagnostic, threshold, clock
        self.guard = threading.Lock()
        self.current: Operation | None = None
        self.last_kind: str | None = None
        self.last_duration: float | None = None
        self.longest_duration = 0.0
        self.slow_count = 0

    def _warn(self, operation):
        with self.guard:
            if self.current is not operation:
                return
            operation.slow = True
            self.slow_count += 1
            message = (
                f"Hardware {operation.kind} exceeded {self.threshold:g} seconds; "
                "the upstream call has not been cancelled"
            )
        try:
            self.diagnostic(message)
        except Exception:
            pass

    @contextmanager
    def track(self, kind):
        # The adapter's hardware lock serializes callers. Nested wrappers retain
        # the outer operation's timer instead of starting competing warnings.
        with self.guard:
            nested = self.current is not None
            if not nested:
                operation = Operation(kind, self.clock())
                self.current = operation
                timer = None
                try:
                    timer = threading.Timer(self.threshold, self._warn, args=(operation,))
                    timer.daemon = True
                    timer.start()
                except Exception:
                    # Diagnostics must never prevent the original hardware call.
                    timer = None
        try:
            yield
        finally:
            if not nested:
                if timer is not None:
                    timer.cancel()
                with self.guard:
                    duration = self.clock() - operation.started
                    self.last_kind, self.last_duration = kind, duration
                    self.longest_duration = max(self.longest_duration, duration)
                    if duration >= self.threshold and not operation.slow:
                        self.slow_count += 1
                    self.current = None

    def status(self):
        with self.guard:
            current = self.current
            elapsed = self.clock() - current.started if current else None
            return {
                "active": current.kind if current else None,
                "elapsed": elapsed,
                "slow": current is not None
                and (current.slow or self.clock() - current.started >= self.threshold),
                "last_kind": self.last_kind,
                "last_duration": self.last_duration,
                "longest_duration": self.longest_duration,
                "slow_count": self.slow_count,
                "warning_seconds": self.threshold,
            }
