"""Tests for terminal notification dismissal."""

import io
import unittest

from alarm_clock.models import Alarm
from alarm_clock.notifications import TerminalNotifier


class TerminalNotifierTests(unittest.TestCase):
    def test_enter_dismisses_and_clears_notification(self) -> None:
        output = io.StringIO()
        notifier = TerminalNotifier(input_function=lambda _prompt: "", output=output)
        alarm = Alarm(
            id="alarm-1",
            date="31-10-2026",
            time="07:30",
            message="Wake up",
        )

        notifier.display(alarm)
        self.assertTrue(notifier._dismissed.wait(timeout=1))
        self.assertTrue(notifier.notification_active)

        notifier.clear()

        self.assertFalse(notifier.notification_active)
        self.assertIn("ALARM: 31-10-2026 07:30 - Wake up", output.getvalue())
        self.assertIn("Notification dismissed.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
