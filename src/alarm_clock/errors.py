"""Application-specific exceptions."""


class AlarmClockError(Exception):
    """Base exception for expected alarm-clock errors."""


class AlarmValidationError(AlarmClockError, ValueError):
    """Raised when an alarm field or status is invalid."""


class AlarmNotFoundError(AlarmClockError):
    """Raised when an operation references an alarm ID that does not exist."""


class AlarmStateError(AlarmClockError):
    """Raised when an operation is not allowed for an alarm's current state."""


class AlarmDataError(AlarmClockError):
    """Raised when persisted alarm data is malformed or unsupported."""


class AlarmStorageError(AlarmClockError):
    """Raised when alarm data cannot be read, locked, or written."""
