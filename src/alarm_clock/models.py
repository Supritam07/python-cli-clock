"""Alarm domain model and input validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from .errors import AlarmValidationError


class AlarmStatus(str, Enum):
    """Lifecycle states supported by an alarm."""

    CREATED = "Created"
    RUNNING = "Running"
    CANCELLED = "Cancelled"
    MISSED = "Missed"
    TRIGGERED = "Triggered"


def _validate_date(value: str) -> None:
    try:
        parsed = datetime.strptime(value, "%d-%m-%Y")
    except (TypeError, ValueError) as exc:
        raise AlarmValidationError(
            "Alarm date must be a valid date in DD-MM-YYYY format."
        ) from exc
    if parsed.strftime("%d-%m-%Y") != value:
        raise AlarmValidationError(
            "Alarm date must be a valid date in DD-MM-YYYY format."
        )


def _validate_time(value: str) -> None:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError) as exc:
        raise AlarmValidationError(
            "Alarm time must be a valid 24-hour time in HH:MM format."
        ) from exc
    if parsed.strftime("%H:%M") != value:
        raise AlarmValidationError(
            "Alarm time must be a valid 24-hour time in HH:MM format."
        )


@dataclass
class Alarm:
    """A one-time alarm scheduled in the computer's local time."""

    id: str
    date: str
    time: str
    message: str | None = None
    status: AlarmStatus = AlarmStatus.CREATED
    created_at: str = field(
        default_factory=lambda: datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
    )

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate fields, including values changed after construction."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise AlarmValidationError("Alarm ID must be a non-empty string.")
        _validate_date(self.date)
        _validate_time(self.time)
        if self.message is not None and not isinstance(self.message, str):
            raise AlarmValidationError("Alarm message must be a string or null.")
        try:
            self.status = AlarmStatus(self.status)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(status.value for status in AlarmStatus)
            raise AlarmValidationError(
                f"Alarm status must be one of: {allowed}."
            ) from exc
        if not isinstance(self.created_at, str):
            raise AlarmValidationError("Alarm creation timestamp must be a string.")
        try:
            datetime.fromisoformat(self.created_at)
        except ValueError as exc:
            raise AlarmValidationError(
                "Alarm creation timestamp must be ISO 8601."
            ) from exc

    @property
    def scheduled_at(self) -> datetime:
        """Return the scheduled local wall-clock datetime."""
        return datetime.strptime(
            f"{self.date} {self.time}", "%d-%m-%Y %H:%M"
        )

    @classmethod
    def create(
        cls,
        date: str,
        time: str,
        message: str | None = None,
        *,
        now: datetime | None = None,
    ) -> Alarm:
        """Create a new alarm after verifying it is scheduled in the future."""
        alarm = cls(
            id=str(uuid4()),
            date=date,
            time=time,
            message=message,
        )
        current_time = now or datetime.now()
        if alarm.scheduled_at <= current_time.replace(tzinfo=None):
            raise AlarmValidationError("Alarm date and time must be in the future.")
        return alarm

    def to_dict(self) -> dict[str, str | None]:
        """Serialize this alarm into the stable JSON record format."""
        return {
            "id": self.id,
            "date": self.date,
            "time": self.time,
            "message": self.message,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: object) -> Alarm:
        """Validate and deserialize a record read from JSON."""
        expected_fields = {
            "id",
            "date",
            "time",
            "message",
            "status",
            "created_at",
        }
        if not isinstance(value, dict):
            raise AlarmValidationError("Each alarm record must be a JSON object.")
        if set(value) != expected_fields:
            missing = expected_fields - set(value)
            extra = set(value) - expected_fields
            details = []
            if missing:
                details.append(f"missing fields: {', '.join(sorted(missing))}")
            if extra:
                details.append(f"unknown fields: {', '.join(sorted(extra))}")
            raise AlarmValidationError(
                "Invalid alarm record (" + "; ".join(details) + ")."
            )
        return cls(
            id=value["id"],
            date=value["date"],
            time=value["time"],
            message=value["message"],
            status=value["status"],
            created_at=value["created_at"],
        )
