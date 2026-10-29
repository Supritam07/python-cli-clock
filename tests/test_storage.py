"""Tests for JSON alarm persistence."""

import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from alarm_clock.errors import AlarmDataError, AlarmValidationError
from alarm_clock.models import Alarm, AlarmStatus
from alarm_clock.storage import JsonAlarmStorage


def _append_alarm_in_process(file_path: str, alarm_id: str) -> None:
    storage = JsonAlarmStorage(file_path)
    alarm = Alarm(
        id=alarm_id,
        date="31-10-2026",
        time="07:30",
        message=alarm_id,
        status=AlarmStatus.CREATED,
        created_at="2026-10-29T16:30:00+05:30",
    )
    storage.update(lambda alarms: alarms.append(alarm))


class JsonAlarmStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.file_path = Path(self.temporary_directory.name) / "nested" / "alarms.json"
        self.storage = JsonAlarmStorage(self.file_path)

    @staticmethod
    def make_alarm(alarm_id: str = "alarm-1") -> Alarm:
        return Alarm(
            id=alarm_id,
            date="31-10-2026",
            time="07:30",
            message="Wake up",
            status=AlarmStatus.CREATED,
            created_at="2026-10-29T16:30:00+05:30",
        )

    def test_default_path_is_project_level_data_file(self) -> None:
        expected = Path(__file__).resolve().parents[1] / "data" / "alarms.json"

        self.assertEqual(JsonAlarmStorage().file_path, expected)

    def test_load_creates_valid_empty_data_file_and_lock(self) -> None:
        self.assertEqual(self.storage.load(), [])
        self.assertTrue(self.file_path.is_file())
        self.assertTrue(self.storage.lock_path.is_file())
        self.assertEqual(
            json.loads(self.file_path.read_text(encoding="utf-8")),
            {"schema_version": 1, "alarms": []},
        )

    def test_update_persists_and_reloads_alarm(self) -> None:
        self.storage.update(lambda alarms: alarms.append(self.make_alarm()))

        self.assertEqual(self.storage.load(), [self.make_alarm()])

    def test_update_reloads_latest_data_before_mutating(self) -> None:
        self.storage.update(lambda alarms: alarms.append(self.make_alarm()))
        self.storage.update(lambda alarms: alarms.append(self.make_alarm("alarm-2")))

        self.assertEqual(
            [alarm.id for alarm in self.storage.load()],
            ["alarm-1", "alarm-2"],
        )

    def test_concurrent_process_updates_are_not_lost(self) -> None:
        processes = [
            multiprocessing.Process(
                target=_append_alarm_in_process,
                args=(str(self.file_path), f"alarm-{index}"),
            )
            for index in range(6)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)

        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
                self.fail("Concurrent alarm writer did not finish in time.")
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(len(self.storage.load()), len(processes))

    def test_duplicate_ids_are_rejected_without_overwriting_file(self) -> None:
        self.storage.update(lambda alarms: alarms.append(self.make_alarm()))
        original_content = self.file_path.read_text(encoding="utf-8")

        with self.assertRaises(AlarmValidationError):
            self.storage.update(lambda alarms: alarms.append(self.make_alarm()))

        self.assertEqual(self.file_path.read_text(encoding="utf-8"), original_content)

    def test_invalid_mutated_record_is_rejected_without_overwriting_file(self) -> None:
        self.storage.update(lambda alarms: alarms.append(self.make_alarm()))
        original_content = self.file_path.read_text(encoding="utf-8")

        def mutate(alarms: list[Alarm]) -> None:
            setattr(alarms[0], "status", "Unknown")

        with self.assertRaises(AlarmValidationError):
            self.storage.update(mutate)

        self.assertEqual(self.file_path.read_text(encoding="utf-8"), original_content)

    def test_malformed_json_is_reported_without_resetting_file(self) -> None:
        self.file_path.parent.mkdir(parents=True)
        self.file_path.write_text("{bad json", encoding="utf-8")

        with self.assertRaises(AlarmDataError):
            self.storage.load()

        self.assertEqual(self.file_path.read_text(encoding="utf-8"), "{bad json")

    def test_invalid_schema_is_reported(self) -> None:
        self.file_path.parent.mkdir(parents=True)
        self.file_path.write_text(
            json.dumps({"schema_version": 99, "alarms": []}),
            encoding="utf-8",
        )

        with self.assertRaises(AlarmDataError):
            self.storage.load()


if __name__ == "__main__":
    unittest.main()
