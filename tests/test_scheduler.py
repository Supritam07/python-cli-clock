"""Tests for alarm polling and scheduler status transitions."""

import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from alarm_clock.errors import AlarmStateError
from alarm_clock.models import Alarm, AlarmStatus
from alarm_clock.scheduler import AlarmScheduler
from alarm_clock.storage import JsonAlarmStorage


class FakeNotifier:
    def __init__(self) -> None:
        self.notification_active = False
        self.dismissed = False
        self.displayed: list[Alarm] = []
        self.cleared = 0

    def display(self, alarm: Alarm) -> None:
        self.displayed.append(alarm)
        self.notification_active = True
        self.dismissed = False

    def is_dismissed(self) -> bool:
        return self.dismissed

    def clear(self) -> None:
        if self.notification_active and self.dismissed:
            self.notification_active = False
            self.dismissed = False
            self.cleared += 1


class AlarmSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.storage = JsonAlarmStorage(
            Path(self.temporary_directory.name) / "data" / "alarms.json"
        )
        self.current_time = datetime(2026, 10, 29, 16, 0)
        self.notifier = FakeNotifier()

    def make_alarm(
        self,
        alarm_id: str,
        scheduled_at: datetime,
        status: AlarmStatus = AlarmStatus.CREATED,
    ) -> Alarm:
        return Alarm(
            id=alarm_id,
            date=scheduled_at.strftime("%d-%m-%Y"),
            time=scheduled_at.strftime("%H:%M"),
            message=alarm_id,
            status=status,
            created_at="2026-10-29T15:00:00",
        )

    def test_startup_marks_old_alarms_missed_and_resets_future_on_exit(self) -> None:
        self.storage.update(
            lambda alarms: alarms.extend(
                [
                    self.make_alarm(
                        "missed", self.current_time - timedelta(minutes=1)
                    ),
                    self.make_alarm(
                        "future", self.current_time + timedelta(minutes=10)
                    ),
                ]
            )
        )
        stop_event = threading.Event()
        stop_event.set()
        scheduler = AlarmScheduler(
            self.storage,
            notifier=self.notifier,
            now=lambda: self.current_time,
            sleep=lambda _delay: None,
        )

        scheduler.run(stop_event)

        statuses = {alarm.id: alarm.status for alarm in self.storage.load()}
        self.assertEqual(statuses["missed"], AlarmStatus.MISSED)
        self.assertEqual(statuses["future"], AlarmStatus.CREATED)
        self.assertEqual(self.notifier.displayed, [])

    def test_due_alarms_are_triggered_queued_and_dismissed_sequentially(self) -> None:
        due_at = self.current_time + timedelta(minutes=1)
        self.storage.update(
            lambda alarms: alarms.extend(
                [self.make_alarm("first", due_at), self.make_alarm("second", due_at)]
            )
        )
        stop_event = threading.Event()
        sleep_count = 0

        def advance(_delay: float) -> None:
            nonlocal sleep_count
            sleep_count += 1
            self.current_time += timedelta(minutes=1)
            if self.notifier.notification_active:
                self.notifier.dismissed = True
            if sleep_count >= 4:
                stop_event.set()

        scheduler = AlarmScheduler(
            self.storage,
            notifier=self.notifier,
            now=lambda: self.current_time,
            sleep=advance,
        )

        scheduler.run(stop_event)

        self.assertEqual(
            [alarm.id for alarm in self.notifier.displayed],
            ["first", "second"],
        )
        self.assertEqual(self.notifier.cleared, 2)
        self.assertEqual(
            {alarm.status for alarm in self.storage.load()},
            {AlarmStatus.TRIGGERED},
        )

    def test_alarm_added_during_run_is_discovered(self) -> None:
        due_at = self.current_time + timedelta(minutes=2)
        stop_event = threading.Event()
        sleep_count = 0

        def external_update(_delay: float) -> None:
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count == 1:
                self.storage.update(
                    lambda alarms: alarms.append(self.make_alarm("external", due_at))
                )
            self.current_time += timedelta(minutes=1)
            if self.notifier.notification_active:
                self.notifier.dismissed = True
            if sleep_count >= 5:
                stop_event.set()

        scheduler = AlarmScheduler(
            self.storage,
            notifier=self.notifier,
            now=lambda: self.current_time,
            sleep=external_update,
        )

        scheduler.run(stop_event)

        self.assertEqual([alarm.id for alarm in self.notifier.displayed], ["external"])
        self.assertEqual(self.storage.load()[0].status, AlarmStatus.TRIGGERED)

    def test_interruption_restores_future_alarms(self) -> None:
        scheduled = self.current_time + timedelta(minutes=5)
        self.storage.update(
            lambda alarms: alarms.append(self.make_alarm("future", scheduled))
        )

        def interrupt(_delay: float) -> None:
            raise KeyboardInterrupt

        scheduler = AlarmScheduler(
            self.storage,
            notifier=self.notifier,
            now=lambda: self.current_time,
            sleep=interrupt,
        )

        with self.assertRaises(KeyboardInterrupt):
            scheduler.run()

        self.assertEqual(self.storage.load()[0].status, AlarmStatus.CREATED)

    def test_second_scheduler_is_rejected(self) -> None:
        from filelock import FileLock

        lock_path = self.storage.file_path.with_name("alarms.json.scheduler.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path)):
            scheduler = AlarmScheduler(
                self.storage,
                notifier=self.notifier,
                now=lambda: self.current_time,
            )
            with self.assertRaises(AlarmStateError):
                scheduler.run()


if __name__ == "__main__":
    unittest.main()
