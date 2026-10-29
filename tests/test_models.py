"""Tests for alarm records and validation."""

import unittest
from datetime import datetime

from alarm_clock.errors import AlarmValidationError
from alarm_clock.models import Alarm, AlarmStatus


class AlarmModelTests(unittest.TestCase):
    def test_create_generates_valid_future_alarm(self) -> None:
        alarm = Alarm.create(
            "31-10-2026",
            "07:30",
            "Wake up",
            now=datetime(2026, 10, 29, 16, 0),
        )

        self.assertTrue(alarm.id)
        self.assertEqual(alarm.status, AlarmStatus.CREATED)
        self.assertEqual(alarm.scheduled_at, datetime(2026, 10, 31, 7, 30))
        self.assertEqual(alarm.message, "Wake up")

    def test_rejects_invalid_date_and_time(self) -> None:
        invalid_inputs = (
            ("31-02-2026", "07:30"),
            ("2026-10-31", "07:30"),
            ("31-10-2026", "24:00"),
            ("31-10-2026", "7:30"),
        )
        for date, time in invalid_inputs:
            with self.subTest(date=date, time=time):
                with self.assertRaises(AlarmValidationError):
                    Alarm.create(
                        date,
                        time,
                        now=datetime(2026, 10, 29, 16, 0),
                    )

    def test_rejects_alarm_not_in_future(self) -> None:
        with self.assertRaisesRegex(AlarmValidationError, "future"):
            Alarm.create(
                "29-10-2026",
                "16:00",
                now=datetime(2026, 10, 29, 16, 0),
            )

    def test_round_trip_record(self) -> None:
        alarm = Alarm(
            id="alarm-1",
            date="31-10-2026",
            time="07:30",
            message=None,
            status=AlarmStatus.RUNNING,
            created_at="2026-10-29T16:30:00+05:30",
        )

        self.assertEqual(Alarm.from_dict(alarm.to_dict()), alarm)

    def test_rejects_unknown_status_and_extra_fields(self) -> None:
        record: dict[str, object] = {
            "id": "alarm-1",
            "date": "31-10-2026",
            "time": "07:30",
            "message": None,
            "status": "Done",
            "created_at": "2026-10-29T16:30:00+05:30",
        }
        with self.assertRaises(AlarmValidationError):
            Alarm.from_dict(record)

        record["status"] = "Created"
        record["extra"] = True
        with self.assertRaises(AlarmValidationError):
            Alarm.from_dict(record)


if __name__ == "__main__":
    unittest.main()
