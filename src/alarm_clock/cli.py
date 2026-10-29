"""Command-line interface for alarm management."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .errors import AlarmClockError
from .models import Alarm
from .scheduler import AlarmScheduler
from .service import AlarmService


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser."""
    parser = argparse.ArgumentParser(
        prog="alarm-clock",
        description="Create and manage alarms from the command line.",
    )
    commands = parser.add_subparsers(dest="command")

    create_parser = commands.add_parser("create", help="create a new alarm")
    create_parser.add_argument(
        "--date",
        required=True,
        metavar="DD-MM-YYYY",
        help="alarm date in day-month-year format",
    )
    create_parser.add_argument(
        "--time",
        required=True,
        metavar="HH:MM",
        help="alarm time in 24-hour local time",
    )
    create_parser.add_argument(
        "--message",
        help="optional message to display when the alarm triggers",
    )

    commands.add_parser("list", help="list saved alarms")

    cancel_parser = commands.add_parser("cancel", help="cancel an alarm")
    cancel_parser.add_argument("alarm_id", help="ID of the alarm to cancel")

    commands.add_parser("run", help="run the alarm scheduler")
    return parser


def _format_alarm(alarm: Alarm) -> str:
    message = alarm.message if alarm.message is not None else "-"
    return (
        f"{alarm.id:<36} {alarm.date:<10} {alarm.time:<5} "
        f"{alarm.status.value:<9} {message}"
    )


def _print_alarms(alarms: list[Alarm]) -> None:
    if not alarms:
        print("No alarms found.")
        return
    print(f"{'ID':<36} {'DATE':<10} {'TIME':<5} {'STATUS':<9} MESSAGE")
    for alarm in alarms:
        print(_format_alarm(alarm))


def main(
    argv: Sequence[str] | None = None,
    *,
    service: AlarmService | None = None,
) -> int:
    """Run a CLI command and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    alarm_service = service or AlarmService()
    try:
        if args.command == "create":
            alarm = alarm_service.create_alarm(args.date, args.time, args.message)
            print(
                f"Created alarm {alarm.id} for {alarm.date} {alarm.time}"
                + (f": {alarm.message}" if alarm.message else "")
            )
            return 0
        if args.command == "list":
            _print_alarms(alarm_service.list_alarms())
            return 0
        if args.command == "cancel":
            alarm = alarm_service.cancel_alarm(args.alarm_id)
            print(f"Cancelled alarm {alarm.id}.")
            return 0
        if args.command == "run":
            try:
                AlarmScheduler().run()
            except KeyboardInterrupt:
                print("\nAlarm scheduler stopped.")
            return 0
    except AlarmClockError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")

    parser.error("unknown command")
    return 2
