"""Terminal alarm notifications with asynchronous Enter dismissal."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from typing import TextIO

from .models import Alarm


class TerminalNotifier:
    """Show one alarm at a time without blocking scheduler polling."""

    def __init__(
        self,
        *,
        input_function: Callable[[str], str] = input,
        output: TextIO | None = None,
    ) -> None:
        self._input = input_function
        self._output = output if output is not None else sys.stdout
        self._dismissed = threading.Event()
        self._input_thread: threading.Thread | None = None
        self.notification_active = False

    def display(self, alarm: Alarm) -> None:
        """Display an alarm and begin waiting for Enter on a daemon thread."""
        message = alarm.message or "(no message)"
        print(
            f"\n*** ALARM: {alarm.date} {alarm.time} - {message} ***",
            file=self._output,
            flush=True,
        )
        self._dismissed.clear()
        self.notification_active = True
        self._input_thread = threading.Thread(
            target=self._wait_for_enter,
            name=f"alarm-dismiss-{alarm.id}",
            daemon=True,
        )
        self._input_thread.start()

    def is_dismissed(self) -> bool:
        """Return whether Enter has been pressed for the current notification."""
        return self._dismissed.is_set()

    def clear(self) -> None:
        """Remove the notification from a terminal or confirm dismissal elsewhere."""
        if not self.notification_active or not self._dismissed.is_set():
            return
        if getattr(self._output, "isatty", lambda: False)():
            self._output.write("\033[2A\033[J")
            self._output.flush()
        else:
            print("Notification dismissed.", file=self._output, flush=True)
        self.notification_active = False
        self._dismissed.clear()

    def _wait_for_enter(self) -> None:
        try:
            self._input("Press Enter to dismiss this alarm...")
        except EOFError:
            pass
        finally:
            self._dismissed.set()
