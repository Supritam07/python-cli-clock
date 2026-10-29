# Alarm Clock CLI — Architecture and Requirements

## 1. Purpose

Build a modular, production-minded alarm clock that runs entirely in the
terminal. The scheduler only operates while the `run` command is active. If the
process or terminal is closed, no alarm notifications are delivered until the
scheduler is started again.

The application uses the computer's **local date and time** for alarm input,
scheduling, comparison, and display.

## 2. Project layout

```text
alarm-clock/
├── ARCHITECTURE.md
├── requirements.txt
├── README.md
├── data/
│   ├── .gitkeep
│   ├── alarms.json
│   └── alarms.json.lock
├── src/
│   └── alarm_clock/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── clock.py
│       ├── errors.py
│       ├── models.py
│       ├── notifications.py
│       ├── scheduler.py
│       ├── service.py
│       └── storage.py
└── tests/
    ├── test_cli.py
    ├── test_models.py
    ├── test_notifications.py
    ├── test_scheduler.py
    ├── test_service.py
    └── test_storage.py
```

`data/alarms.json` is created automatically when the app first needs to save
alarm data. The `data` directory is at the level of the `alarm-clock` project
folder. Resolve it from the project/package location, not from the process's
current working directory, so launching the command from another directory
still uses the same file. The lock file is kept alongside the JSON file.

Do not commit user alarm data or lock files. `.gitignore` excludes
`data/alarms.json`, `data/alarms.json.lock`, and
`data/alarms.json.scheduler.lock`; `.gitkeep` can preserve the empty data
directory in version control.

## 3. Module responsibilities

| Module | Responsibility |
|---|---|
| `__main__.py` | Application entry point; supports `python -m alarm_clock`. |
| `cli.py` | Parse commands and arguments, invoke the service, and print clear output. Use `argparse` unless the project has a reason to choose another CLI library. |
| `models.py` | Define the alarm model, status values, serialization, and validation rules. |
| `clock.py` | Provide local current time and date operations through an injectable clock interface for deterministic tests. |
| `errors.py` | Define application errors for invalid input/data, missing alarms, and storage failures. |
| `storage.py` | Read, validate, and safely update the JSON file; provide coordination between app processes. |
| `service.py` | Implement use cases: create, list, cancel, and reconcile alarms. |
| `scheduler.py` | Poll for due alarms, reload external changes, manage status transitions, and respond to shutdown. |
| `notifications.py` | Display queued notifications, wait for Enter dismissal, and clear the displayed notification. |

Keep dependencies directed toward the core: the CLI calls the service; the
service uses models and storage; the scheduler coordinates the service,
storage, clock, and notification handling. Models and clock logic should not
depend on the CLI.

## 4. CLI commands

Example command interface:

```text
python -m alarm_clock create --date 31-10-2026 --time 07:30 --message "Wake up"
python -m alarm_clock list
python -m alarm_clock cancel <alarm-id>
python -m alarm_clock run
```

- `create` accepts a date in `DD-MM-YYYY`, a 24-hour time in `HH:MM`, and an
  optional message.
- `list` shows each alarm's ID, local date/time, message, and status.
- `cancel` cancels an eligible alarm by ID.
- `run` starts the scheduler and remains active until interrupted with
  **Ctrl+C**.

Commands should report invalid input, unknown IDs, invalid JSON, and storage
problems clearly. Errors must not be presented as successful operations.

## 5. Alarm model and statuses

Each alarm contains:

- A unique, stable ID.
- A local scheduled date and time.
- An optional notification message.
- A status.
- A creation timestamp.

Allowed statuses:

| Status | Meaning |
|---|---|
| `Created` | Saved and waiting for its scheduled time. |
| `Running` | The active scheduler is monitoring the alarm. |
| `Cancelled` | Cancelled before it was triggered. |
| `Missed` | Its scheduled time passed while the scheduler was not running. |
| `Triggered` | Its scheduled time arrived while the scheduler was running; its notification is queued or has been shown. |

Use `Triggered` as the one fired-alarm status; do not maintain a second
`Completed` status. Notification dismissal is separate from alarm status.

Valid status transitions:

```text
Created -> Running -> Triggered
Created -> Cancelled
Running -> Cancelled
Running -> Created   (scheduler stops before the alarm is due)
Created/Running -> Missed   (scheduled time passed while not actively monitored)
```

`Cancelled`, `Missed`, and `Triggered` are terminal statuses. A triggered alarm
is not cancelled by pressing Enter.

## 6. Scheduler and notification behavior

1. `run` loads and validates the alarm file.
2. Reconcile alarms left as `Running` by an earlier scheduler process. A
   future alarm returns to `Created` before monitoring; an alarm whose time
   passed while the scheduler was stopped becomes `Missed`.
3. Mark eligible future alarms `Running`.
4. Periodically reload the JSON file so changes made by another app process
   are discovered.
5. When an alarm is due, persist its `Triggered` status and queue its
   notification before displaying it. This prevents a restart from firing the
   same alarm again.
6. Display the notification in the terminal and wait for the user to press
   **Enter**. On Enter, clear or remove the displayed notification and resume
   normal scheduler checks.
7. The scheduler must continue tracking time while a notification is awaiting
   dismissal. If other alarms become due meanwhile, queue them and show each
   after the current notification is dismissed; do not drop alarms.
8. **Ctrl+C** requests graceful shutdown. Stop polling, preserve all persisted
   alarm data, and return future alarms still being monitored to `Created`.
   Do not mark future alarms `Missed` just because the user exited.

Only terminal notifications are required; desktop or mobile notifications are
out of scope.

## 7. Persistence and concurrent access

Store alarms as JSON in:

```text
<alarm-clock project folder>/data/alarms.json
```

Create the parent directory and a valid initial JSON document automatically
when needed. Keep the process coordination file at:

```text
<alarm-clock project folder>/data/alarms.json.lock
```

The scheduler also holds `data/alarms.json.scheduler.lock` for the duration of
`run`, preventing multiple scheduler processes from firing the same alarm.

All app commands that modify alarm data must use the same storage layer. To
avoid lost updates when the scheduler and another CLI command run
simultaneously:

- Acquire a process-safe lock for each read-modify-write operation.
- Reload current data after acquiring the lock rather than writing a stale
  in-memory snapshot.
- Validate the JSON document and alarm records before applying changes.
- Write to a temporary file in the same directory, flush it, and atomically
  replace `alarms.json` only after the write succeeds.
- Report malformed JSON or invalid records explicitly; do not silently reset
  or discard the user's data.

Schema version 1 uses this structure. Dates are `DD-MM-YYYY`, times are
24-hour `HH:MM`, and `created_at` is an ISO 8601 local timestamp:

```json
{
  "schema_version": 1,
  "alarms": [
    {
      "id": "unique-id",
      "date": "31-10-2026",
      "time": "07:30",
      "message": "Wake up",
      "status": "Created",
      "created_at": "2026-10-29T16:30:00+05:30"
    }
  ]
}
```

The scheduler periodically reloads the file to discover alarm changes made by
another CLI process. Manual edits to the JSON file can also be detected, but
CLI commands are the supported, safer way to update it because they use the
file lock and validation rules.

## 8. Time rules

- Interpret dates and times as computer-local time; no timezone selection or
  conversion is part of the initial requirements.
- Reject malformed dates, malformed 24-hour times, and alarms scheduled in the
  past at creation time.
- Re-read the current local time on each scheduler poll rather than relying
  only on a long-running sleep calculated once.
- Keep time access behind `clock.py` so clock changes and boundary cases can
  be tested. The initial implementation should compare against the computer's
  current local wall-clock time; document that changing the system clock can
  affect when alarms are observed.

## 9. Reliability and error handling

- Validate IDs, required fields, date/time values, and status values both on
  CLI input and when loading JSON.
- Ensure a triggered notification is persisted before it is shown.
- Handle Ctrl+C as an expected clean-shutdown path.
- Surface filesystem, locking, and JSON errors with actionable messages.
- Avoid broad exception handling, silent defaults, or success-shaped fallback
  behavior.

## 10. Testing plan

- **Models:** valid/invalid dates and times, serialization, IDs, and statuses.
- **Storage:** initial file creation, JSON validation, atomic writes, and
  concurrent read-modify-write behavior.
- **Service:** create/list/cancel rules and status transitions.
- **Scheduler:** due alarms, missed alarms, reloads from external CLI changes,
  multiple due alarms, shutdown, and restart reconciliation.
- **Notifications:** Enter dismissal, notification clearing, and queued alarm
  handling.
- **CLI:** command parsing and user-visible success/error cases.

Inject a fake clock and controllable input/output into scheduler and
notification tests. Tests should not depend on real-time waits or the user's
actual alarm data.

## 11. Acceptance criteria

1. A valid future alarm is saved to `data/alarms.json` and appears in `list`.
2. Invalid date/time input and past alarm times are rejected with a helpful
   error.
3. Cancelling an eligible alarm updates the JSON file and list output; terminal
   alarms cannot be cancelled.
4. While `run` is active, due alarms are marked `Triggered` and their terminal
   notifications are displayed.
5. Enter dismisses and clears the current notification without stopping the
   scheduler.
6. Alarms becoming due while another notification is awaiting Enter are queued
   and subsequently displayed.
7. An alarm that passed while the scheduler was stopped is marked `Missed`
   when the app next reconciles alarm data.
8. Changes made through another CLI process are picked up by the running
   scheduler without losing concurrent updates.
9. Ctrl+C exits cleanly, preserves data, and does not mark future alarms
   missed.
10. The app uses the same project-level `data/alarms.json` regardless of the
    command's current working directory.
