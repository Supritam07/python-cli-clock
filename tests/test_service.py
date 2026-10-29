"""Tests for alarm application use cases."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from alarm_clock.errors import AlarmNotFoundError, AlarmStateError
from alarm_clock.models import AlarmStatus
from alarm_clock.service import AlarmService
from alarm_clock.storage import JsonAlarmStorage


class AlarmServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.now = datetime(2026, 10, 29, 16, 0)
        self.storage = JsonAlarmStorage(
            Path(self.temporary_directory.name) / "alarms.json"
        )
        self.service = AlarmService(self.storage, now=lambda: self.now)

    def create_alarm(self, days_ahead: int = 1, message: str | None = None):
        scheduled = self.now + timedelta(days=days_ahead)
        return self.service.create_alarm(
            scheduled.strftime("%d-%m-%Y"),
            scheduled.strftime("%H:%M"),
            message,
        )

    def test_create_and_list_alarms_in_schedule_order(self) -> None:
        later = self.create_alarm(days_ahead=2)
        earlier = self.create_alarm(days_ahead=1, message="Wake up")

        alarms = self.service.list_alarms()
        self.assertEqual([alarm.id for alarm in alarms], [earlier.id, later.id])
        self.assertEqual(alarms[0].status, AlarmStatus.CREATED)
        self.assertEqual(alarms[0].message, "Wake up")

    def test_cancel_created_alarm_persists_cancelled_status(self) -> None:
        alarm = self.create_alarm()

        cancelled = self.service.cancel_alarm(alarm.id)

        self.assertEqual(cancelled.status, AlarmStatus.CANCELLED)
        self.assertEqual(self.service.list_alarms()[0].status, AlarmStatus.CANCELLED)

    def test_cancel_running_alarm(self) -> None:
        alarm = self.create_alarm()
        self.storage.update(
            lambda alarms: setattr(alarms[0], "status", AlarmStatus.RUNNING)
        )

        self.assertEqual(
            self.service.cancel_alarm(alarm.id).status,
            AlarmStatus.CANCELLED,
        )

    def test_cancel_unknown_or_terminal_alarm_reports_error(self) -> None:
        with self.assertRaises(AlarmNotFoundError):
            self.service.cancel_alarm("missing")

        alarm = self.create_alarm()
        self.service.cancel_alarm(alarm.id)
        with self.assertRaises(AlarmStateError):
            self.service.cancel_alarm(alarm.id)


if __name__ == "__main__":
    unittest.main()
