"""Error and warning types for the slmp package."""

from __future__ import annotations


class SlmpError(Exception):
    """SLMP protocol error or error response."""

    def __init__(self, message: str, *, end_code: int | None = None, data: bytes = b"") -> None:
        """Initialize SlmpError with message, optional end code and response data."""
        super().__init__(message)
        self.end_code = end_code
        self.data = data


class SlmpUnsupportedDeviceError(ValueError):
    """Project-level validation error for device families intentionally disabled in typed APIs."""


class SlmpPracticalPathWarning(UserWarning):
    """Warning for paths that are implemented but known to be problematic on validated targets."""


class SlmpBoundaryBehaviorWarning(UserWarning):
    """Warning for target-specific boundary behavior that may differ from simple range assumptions."""
