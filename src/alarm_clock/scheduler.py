"""Alarm polling, status reconciliation, and notification scheduling."""

from __future__ import annotations

import time
import threading
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from filelock import FileLock, Timeout

from .clock import local_now
from .errors import AlarmStateError, AlarmStorageError
from .models import Alarm, AlarmStatus
from .notifications import TerminalNotifier
from .storage import JsonAlarmStorage

DEFAULT_POLL_INTERVAL = 0.5


class Notifier(Protocol):
    """Notification operations required by the scheduler."""

    notification_active: bool

    def display(self, alarm: Alarm) -> None: ...

    def is_dismissed(self) -> bool: ...

    def clear(self) -> None: ...


class AlarmScheduler:
    """Monitor persisted alarms and emit terminal notifications while running."""

    def __init__(
        self,
        storage: JsonAlarmStorage | None = None,
        *,
        notifier: Notifier | None = None,
        now: Callable[[], datetime] = local_now,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("Scheduler poll interval must be greater than zero.")
        self.storage = storage or JsonAlarmStorage()
        self.notifier = notifier or TerminalNotifier()
        self._now = now
        self._sleep = sleep
        self.poll_interval = poll_interval
        self._active_ids: set[str] = set()
        self._queue: deque[Alarm] = deque()

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Run until the stop event is set or the caller interrupts the process."""
        event = stop_event or threading.Event()
        scheduler_lock = FileLock(
            str(
                self.storage.file_path.with_name(
                    self.storage.file_path.name + ".scheduler.lock"
                )
            ),
            timeout=0,
        )
        self.storage.load()
        try:
            scheduler_lock.acquire()
        except Timeout as exc:
            raise AlarmStateError(
                "Another alarm scheduler is already running for this data file."
            ) from exc
        except OSError as exc:
            raise AlarmStorageError("Could not acquire the scheduler lock.") from exc

        try:
            self._initialize()
            print("Alarm scheduler running. Press Ctrl+C to exit.")
            while not event.is_set():
                self._poll()
                self._sleep(self.poll_interval)
        finally:
            try:
                self._reset_active_alarms()
            finally:
                scheduler_lock.release()

    def _initialize(self) -> None:
        """Reconcile alarms left by a previous process and start monitoring."""
        now = self._now()
        self._active_ids.clear()
        self._queue.clear()

        def reconcile(alarms: list[Alarm]) -> None:
            for alarm in alarms:
                if alarm.status not in (AlarmStatus.CREATED, AlarmStatus.RUNNING):
                    continue
                if alarm.scheduled_at <= now:
                    alarm.status = AlarmStatus.MISSED
                else:
                    alarm.status = AlarmStatus.RUNNING
                    self._active_ids.add(alarm.id)

        self.storage.update(reconcile)

    def _poll(self) -> None:
        """Reload, reconcile, and enqueue alarms that became due while monitored."""
        now = self._now()
        triggered: list[Alarm] = []

        def reconcile(alarms: list[Alarm]) -> None:
            for alarm in alarms:
                if alarm.status not in (AlarmStatus.CREATED, AlarmStatus.RUNNING):
                    self._active_ids.discard(alarm.id)
                    continue
                if alarm.scheduled_at > now:
                    alarm.status = AlarmStatus.RUNNING
                    self._active_ids.add(alarm.id)
                elif alarm.id in self._active_ids:
                    alarm.status = AlarmStatus.TRIGGERED
                    triggered.append(alarm)
                    self._active_ids.discard(alarm.id)
                else:
                    alarm.status = AlarmStatus.MISSED

        self.storage.update(reconcile)
        self._queue.extend(triggered)

        if self.notifier.notification_active and self.notifier.is_dismissed():
            self.notifier.clear()
        if self._queue and not self.notifier.notification_active:
            self.notifier.display(self._queue.popleft())

    def _reset_active_alarms(self) -> None:
        """Return still-future alarms monitored by this run to Created."""
        active_ids = set(self._active_ids)
        self._active_ids.clear()
        if not active_ids:
            return
        now = self._now()

        def reset(alarms: list[Alarm]) -> None:
            for alarm in alarms:
                if alarm.id in active_ids and alarm.status == AlarmStatus.RUNNING:
                    alarm.status = (
                        AlarmStatus.MISSED
                        if alarm.scheduled_at <= now
                        else AlarmStatus.CREATED
                    )

        self.storage.update(reset)
