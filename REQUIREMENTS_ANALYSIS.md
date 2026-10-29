# Alarm Clock CLI — Requirements Analysis

## 1. Overview

The application is a Python command-line alarm clock. Users create and manage
alarms through CLI commands, while a separately invoked scheduler monitors
saved alarms and prints terminal notifications. The scheduler only delivers
notifications while its `run` process is active.

Alarm dates and times use the computer's local date and time. Alarm data is
persisted as JSON in the project-level `data/alarms.json` file.

## 2. Users and operating context

- **Alarm owner:** creates, lists, and cancels alarms from a terminal.
- **Scheduler operator:** starts `run` in a terminal and leaves it running to
  receive notifications.
- **Multiple CLI processes:** users may create or update alarms from another
  terminal while the scheduler is active.

The initial application is single-user and local to one project installation.
It does not provide a network service, background daemon, or notification
delivery after the scheduler process stops.

## 3. Functional requirements

### FR-1: Create an alarm

- The user can create an alarm with a date in `DD-MM-YYYY` format and a time
  in 24-hour `HH:MM` format.
- The user may provide an optional message for the notification.
- The application validates the date and time and rejects invalid or past
  scheduled times.
- A successfully created alarm receives a unique ID and is saved to JSON.
- Date/time input is interpreted in the computer's local time.

### FR-2: List alarms

- The user can list saved alarms.
- Each listed alarm shows its ID, scheduled local date and time, optional
  message, and current status.
- The command reads current persisted data so changes from other CLI
  processes are reflected.

### FR-3: Cancel an alarm

- The user can cancel an alarm by ID before it has triggered.
- Cancellation updates persisted data and is visible in the next list.
- The application reports an unknown ID or an alarm that is no longer
  cancellable with a clear error.
- Cancelled alarms do not trigger notifications.

### FR-4: Persist alarm data

- Alarm records are stored in `<alarm-clock project folder>/data/alarms.json`.
- The application creates the `data` directory and JSON file when required.
- The path is anchored to the project/package location, not the current
  working directory.
- Alarm records remain available after the CLI process exits or restarts.
- Invalid JSON or invalid records are reported; the application must not
  silently discard or overwrite user data.

### FR-5: Observe changes from other CLI processes

- The running scheduler periodically reloads persisted alarms.
- Alarms created or changed by another CLI process are detected without
  restarting the scheduler.
- Concurrent updates must not overwrite one another. App writes use shared
  locking and safe atomic replacement.
- Direct manual edits may be observed on reload, but supported updates should
  use the CLI so validation and locking are applied.

### FR-6: Run the scheduler

- The user starts alarm monitoring explicitly with the `run` command.
- The scheduler checks for due alarms and prints notifications while it is
  running.
- Notifications are terminal output only.
- If an alarm's scheduled time passes while the scheduler was not running,
  it is marked `Missed` at the next reconciliation and is not presented as
  though it fired.
- The scheduler reloads persisted data periodically to incorporate updates.

### FR-7: Dismiss notifications

- When an alarm is due, the scheduler displays its notification and waits for
  the user to press Enter to dismiss it.
- Enter clears or removes the current notification and returns the scheduler
  to checking for upcoming alarms.
- The scheduler continues tracking alarms while a notification awaits
  dismissal. Other due alarms are queued and displayed after the current
  notification is dismissed; none are silently dropped.
- Dismissing a notification does not change the alarm's `Triggered` status.

### FR-8: Exit cleanly

- Ctrl+C stops the alarm application cleanly.
- Shutdown preserves alarm data and does not mark future alarms missed.
- Future alarms being monitored are returned to `Created` when the scheduler
  shuts down normally.
- An unexpected process termination may leave alarms marked `Running`; the
  next scheduler startup reconciles those records.

## 4. Alarm statuses and lifecycle

| Status | Definition |
|---|---|
| `Created` | Persisted and waiting for its scheduled time. |
| `Running` | Currently being monitored by the active scheduler. |
| `Cancelled` | Cancelled before triggering. |
| `Missed` | Its scheduled time passed while the scheduler was not monitoring it. |
| `Triggered` | Its scheduled time arrived while monitored; notification is queued, displayed, or dismissed. |

Expected transitions:

```text
Created -> Running -> Triggered
Created -> Cancelled
Running -> Cancelled
Running -> Created   (normal shutdown before scheduled time)
Created/Running -> Missed   (scheduled time passed while not monitored)
```

`Cancelled`, `Missed`, and `Triggered` are terminal statuses. Notification
dismissal is notification state, not a separate alarm status. There is one
fired status (`Triggered`), not separate `Triggered` and `Completed` values.

## 5. Data requirements

Each JSON alarm record must contain:

- `id`: unique stable identifier.
- `date`: local scheduled date, represented in a documented consistent format.
- `time`: local scheduled time, represented in a documented consistent format.
- `message`: optional string.
- `status`: one of the defined status values.
- `created_at`: creation timestamp.

The JSON document must have a documented top-level structure and a schema
version so it can be validated and evolved deliberately. Notification queue
state, if persisted, must be designed so that an already-triggered alarm is
not accidentally fired a second time after restart.

Locking metadata belongs in `data/alarms.json.lock`, beside the JSON data file.
Alarm data and the lock file must be excluded from version control; the empty
`data` directory may be retained with a `.gitkeep` file.

## 6. Non-functional requirements

### Reliability

- Persist a triggered status before displaying its notification to avoid
  duplicate delivery after restart.
- Use a process-safe lock for read-modify-write operations.
- Write to a temporary file in the same directory and atomically replace the
  JSON file only after a successful write.
- Report file access, lock, malformed JSON, and invalid-data errors clearly.

### Responsiveness

- Scheduler polling and JSON reload intervals should be configurable as
  internal constants initially and short enough for prompt notification and
  external-change detection.
- Waiting for Enter must not prevent the scheduler from discovering alarms
  that become due.

### Maintainability and testability

- Separate CLI, domain model, service operations, storage, clock, scheduler,
  and notifications into distinct Python modules.
- Inject the clock and terminal input/output so scheduler behavior can be
  tested without real waiting or terminal interaction.
- Keep core domain logic independent of CLI parsing and presentation.

### Portability

- Use local system time consistently for alarm interpretation and display.
- Document any platform limitations in process locking or terminal-clearing
  behavior.

## 7. CLI scope

Initial command examples:

```text
python -m alarm_clock create --date 31-10-2026 --time 07:30 --message "Wake up"
python -m alarm_clock list
python -m alarm_clock cancel <alarm-id>
python -m alarm_clock run
```

No desktop/mobile notification integration, snooze, recurring alarms,
time-zone selection, network synchronization, or user accounts are required
for the initial version.

## 8. Assumptions and decisions

1. The application is intended to run locally from its project folder.
2. The scheduler must be explicitly started and is not installed as a system
   service.
3. Alarm times are local wall-clock values; daylight-saving transitions and
   manual system-clock changes can affect when an alarm is observed.
4. `Triggered` is the canonical status for an alarm that fired; Enter only
   dismisses its notification.
5. If several alarms become due before the user presses Enter, notifications
   are queued and shown sequentially.
6. File edits made outside the app are not guaranteed safe under concurrent
   writes; the CLI is the supported mutation interface.

## 9. Acceptance criteria

1. Creating a valid future alarm saves it to `data/alarms.json`, assigns an ID,
   and makes it visible in `list`.
2. Invalid dates, invalid times, and past times are rejected with an
   actionable message.
3. Cancelling an eligible alarm persists `Cancelled`; attempting to cancel an
   unknown or terminal alarm reports an error.
4. Running the scheduler causes due alarms to become `Triggered` and displays
   their messages in the terminal.
5. Enter dismisses and clears the active notification while the scheduler
   continues to run.
6. Alarms becoming due during a pending notification are queued and displayed
   after dismissal.
7. An alarm that passed while the scheduler was stopped becomes `Missed` on
   startup reconciliation.
8. A future alarm added through another CLI process is detected by the
   running scheduler without losing concurrent changes.
9. Ctrl+C exits cleanly, preserves data, and leaves future alarms available
   for a later scheduler run.
10. Running commands from a different current working directory still uses
    the project-level `data/alarms.json`.
