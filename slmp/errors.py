"""Error and warning types for the slmp package."""

from __future__ import annotations

from .error_codes import get_end_code_message, get_end_code_name, is_remote_password_end_code


class SlmpError(Exception):
    """SLMP protocol error or error response."""

    def __init__(self, message: str, *, end_code: int | None = None, data: bytes = b"") -> None:
        """Initialize SlmpError with message, optional end code and response data."""
        super().__init__(message)
        self.end_code = end_code
        self.data = data

    @property
    def end_code_name(self) -> str | None:
        """Return a compact symbolic name for the SLMP end code, if present."""
        return get_end_code_name(self.end_code) if self.end_code is not None else None

    @property
    def end_code_message(self) -> str | None:
        """Return the English SLMP end-code message, if present."""
        return get_end_code_message(self.end_code) if self.end_code is not None else None

    @property
    def is_remote_password_error(self) -> bool:
        """Return True when this error is related to remote password protection."""
        return self.end_code is not None and is_remote_password_end_code(self.end_code)


class SlmpUnsupportedDeviceError(ValueError):
    """Project-level validation error for device families intentionally disabled in typed APIs."""


class SlmpPracticalPathWarning(UserWarning):
    """Warning for paths that are implemented but known to be problematic on validated targets."""


class SlmpBoundaryBehaviorWarning(UserWarning):
    """Warning for target-specific boundary behavior that may differ from simple range assumptions."""
