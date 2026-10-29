# Alarm Clock CLI

A modular Python command-line alarm clock. See
[ARCHITECTURE.md](./ARCHITECTURE.md) and
[REQUIREMENTS_ANALYSIS.md](./REQUIREMENTS_ANALYSIS.md) for the architecture and
requirements.

## Development setup

```bash
python3 -m venv clock-venv
source clock-venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONPATH=src
python -m alarm_clock --help
```

## Alarm commands

Run these commands from the project directory after completing the setup
above:

```bash
python -m alarm_clock create --date 31-10-2026 --time 07:30 --message "Wake up"
python -m alarm_clock list
python -m alarm_clock cancel <alarm-id>
python -m alarm_clock run
```

Alarms are stored in the project's `data/alarms.json` file. Date and time
arguments use the computer's local date and time. Keep `run` active in a
terminal to monitor alarms. Due alarms are queued, displayed, and dismissed
with Enter; use Ctrl+C to stop the scheduler cleanly.

Run the test suite from the project directory with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests use temporary alarm files and do not modify `data/alarms.json`.

## Current limitations

- Alarms are one-time only; recurring alarms and snooze are not implemented.
- Notifications are terminal-only and are delivered only while `run` is active.
  An alarm that passes while the scheduler is stopped is marked `Missed` the
  next time the scheduler starts.
- Scheduling uses local wall-clock time, so system clock or daylight-saving
  changes can affect when an alarm is observed.
- Keep the data directory private to the user account; the JSON file is not
  encrypted. Update it through the CLI rather than editing it manually while
  the application is running.
