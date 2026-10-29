"""Use cases for creating, listing, and cancelling alarms."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .errors import AlarmNotFoundError, AlarmStateError
from .models import Alarm, AlarmStatus
from .storage import JsonAlarmStorage


class AlarmService:
    """Coordinate alarm operations through validated persistent storage."""

    def __init__(
        self,
        storage: JsonAlarmStorage | None = None,
        *,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._storage = storage or JsonAlarmStorage()
        self._now = now

    def create_alarm(
        self,
        date: str,
        time: str,
        message: str | None = None,
    ) -> Alarm:
        """Validate and persist an alarm scheduled in the future."""
        def create(alarms: list[Alarm]) -> Alarm:
            alarm = Alarm.create(date, time, message, now=self._now())
            alarms.append(alarm)
            return alarm

        return self._storage.update(create)

    def list_alarms(self) -> list[Alarm]:
        """Return persisted alarms ordered by scheduled time and ID."""
        return sorted(
            self._storage.load(),
            key=lambda alarm: (alarm.scheduled_at, alarm.id),
        )

    def cancel_alarm(self, alarm_id: str) -> Alarm:
        """Cancel an alarm that has not triggered or otherwise terminated."""
        def cancel(alarms: list[Alarm]) -> Alarm:
            alarm = next((item for item in alarms if item.id == alarm_id), None)
            if alarm is None:
                raise AlarmNotFoundError(f"No alarm found with ID '{alarm_id}'.")
            if alarm.status not in (AlarmStatus.CREATED, AlarmStatus.RUNNING):
                raise AlarmStateError(
                    f"Alarm '{alarm_id}' cannot be cancelled because its status "
                    f"is {alarm.status.value}."
                )
            alarm.status = AlarmStatus.CANCELLED
            return alarm

        return self._storage.update(cancel)
