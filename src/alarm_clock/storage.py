"""Locked, atomic JSON persistence for alarm records."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, TypeVar

from filelock import FileLock, Timeout

from .errors import AlarmDataError, AlarmStorageError, AlarmValidationError
from .models import Alarm

SCHEMA_VERSION = 1
T = TypeVar("T")


class JsonAlarmStorage:
    """Persist alarms in a project-level JSON file with process-safe locking."""

    def __init__(
        self,
        file_path: str | Path | None = None,
        *,
        lock_timeout: float = 10,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.file_path = (
            Path(file_path)
            if file_path is not None
            else project_root / "data" / "alarms.json"
        )
        self.lock_path = self.file_path.with_name(self.file_path.name + ".lock")
        self.lock_timeout = lock_timeout

    def load(self) -> list[Alarm]:
        """Return the current alarms, creating a valid empty file if absent."""
        self._ensure_parent()
        with self._locked():
            if not self.file_path.exists():
                self._write_unlocked([])
            return self._read_unlocked()

    def update(self, mutator: Callable[[list[Alarm]], T]) -> T:
        """Apply a read-modify-write operation under one exclusive file lock."""
        self._ensure_parent()
        with self._locked():
            if not self.file_path.exists():
                self._write_unlocked([])
            alarms = self._read_unlocked()
            result = mutator(alarms)
            self._validate_collection(alarms)
            self._write_unlocked(alarms)
            return result

    @contextmanager
    def _locked(self) -> Generator[None, None, None]:
        lock = FileLock(str(self.lock_path), timeout=self.lock_timeout)
        try:
            lock.acquire()
        except Timeout as exc:
            raise AlarmStorageError(
                "Timed out waiting for the alarm data lock."
            ) from exc
        except OSError as exc:
            raise AlarmStorageError(
                f"Could not acquire alarm data lock '{self.lock_path}'."
            ) from exc
        try:
            yield
        finally:
            lock.release()

    def _ensure_parent(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AlarmStorageError(
                f"Could not create alarm data directory '{self.file_path.parent}'."
            ) from exc

    def _read_unlocked(self) -> list[Alarm]:
        try:
            with self.file_path.open("r", encoding="utf-8") as data_file:
                document = json.load(data_file)
        except json.JSONDecodeError as exc:
            raise AlarmDataError(
                f"Alarm data file '{self.file_path}' contains invalid JSON."
            ) from exc
        except UnicodeDecodeError as exc:
            raise AlarmDataError(
                f"Alarm data file '{self.file_path}' is not valid UTF-8."
            ) from exc
        except OSError as exc:
            raise AlarmStorageError(
                f"Could not read alarm data file '{self.file_path}'."
            ) from exc

        if not isinstance(document, dict):
            raise AlarmDataError("Alarm data must be a JSON object.")
        if set(document) != {"schema_version", "alarms"}:
            raise AlarmDataError(
                "Alarm data must contain only 'schema_version' and 'alarms'."
            )
        version = document["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise AlarmDataError(
                f"Unsupported alarm data schema version: {version!r}."
            )
        records = document["alarms"]
        if not isinstance(records, list):
            raise AlarmDataError("'alarms' must be a JSON array.")

        alarms: list[Alarm] = []
        for index, record in enumerate(records):
            try:
                alarms.append(Alarm.from_dict(record))
            except AlarmValidationError as exc:
                raise AlarmDataError(f"Invalid alarm at index {index}: {exc}") from exc
        try:
            self._validate_collection(alarms)
        except AlarmValidationError as exc:
            raise AlarmDataError(str(exc)) from exc
        return alarms

    @staticmethod
    def _validate_collection(alarms: list[Alarm]) -> None:
        if not all(isinstance(alarm, Alarm) for alarm in alarms):
            raise AlarmValidationError("Alarm storage updates must contain Alarm records.")
        for alarm in alarms:
            alarm.validate()
        ids = [alarm.id for alarm in alarms]
        if len(ids) != len(set(ids)):
            raise AlarmValidationError("Alarm IDs must be unique.")

    def _write_unlocked(self, alarms: list[Alarm]) -> None:
        document = {
            "schema_version": SCHEMA_VERSION,
            "alarms": [alarm.to_dict() for alarm in alarms],
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.file_path.parent,
                prefix=f".{self.file_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(document, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.file_path)
        except (OSError, TypeError, ValueError) as exc:
            raise AlarmStorageError(
                f"Could not safely write alarm data file '{self.file_path}'."
            ) from exc
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError as exc:
                    raise AlarmStorageError(
                        f"Could not remove temporary alarm file '{temporary_path}'."
                    ) from exc
