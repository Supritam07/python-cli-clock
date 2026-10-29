"""Tests for alarm command-line behavior."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from alarm_clock.cli import main
from alarm_clock.service import AlarmService
from alarm_clock.storage import JsonAlarmStorage


class AlarmCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.now = datetime(2026, 10, 29, 16, 0)
        storage = JsonAlarmStorage(Path(self.temporary_directory.name) / "alarms.json")
        self.service = AlarmService(storage, now=lambda: self.now)
        scheduled = self.now + timedelta(days=1)
        self.date = scheduled.strftime("%d-%m-%Y")
        self.time = scheduled.strftime("%H:%M")

    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                status = main(arguments, service=self.service)
            except SystemExit as exc:
                status = int(exc.code)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_create_list_and_cancel_commands(self) -> None:
        status, created_output, _ = self.invoke(
            [
                "create",
                "--date",
                self.date,
                "--time",
                self.time,
                "--message",
                "Wake up",
            ]
        )
        self.assertEqual(status, 0)
        self.assertIn("Created alarm", created_output)

        status, list_output, _ = self.invoke(["list"])
        self.assertEqual(status, 0)
        self.assertIn("Wake up", list_output)
        alarm_id = self.service.list_alarms()[0].id

        status, cancelled_output, _ = self.invoke(["cancel", alarm_id])
        self.assertEqual(status, 0)
        self.assertIn("Cancelled alarm", cancelled_output)

    def test_invalid_alarm_is_reported_as_cli_error(self) -> None:
        status, _, error_output = self.invoke(
            ["create", "--date", "31-02-2026", "--time", "07:30"]
        )

        self.assertEqual(status, 2)
        self.assertIn("valid date", error_output)

    def test_unknown_alarm_cancel_is_reported_as_cli_error(self) -> None:
        status, _, error_output = self.invoke(["cancel", "missing-id"])

        self.assertEqual(status, 2)
        self.assertIn("No alarm found", error_output)

    def test_run_handles_ctrl_c_as_clean_exit(self) -> None:
        stdout = io.StringIO()
        with patch("alarm_clock.cli.AlarmScheduler") as scheduler_class:
            scheduler_class.return_value.run.side_effect = KeyboardInterrupt
            with redirect_stdout(stdout):
                status = main(["run"], service=self.service)

        self.assertEqual(status, 0)
        self.assertIn("Alarm scheduler stopped.", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
