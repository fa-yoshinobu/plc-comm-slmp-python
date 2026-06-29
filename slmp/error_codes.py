"""SLMP end-code keys and categories."""

from __future__ import annotations

from typing import Literal

SlmpEndCodeLanguage = Literal["en", "ja"]

_REMOTE_PASSWORD_END_CODES = {
    0xC200,
    0xC201,
    0xC202,
    0xC203,
    0xC204,
    0xC205,
    0xC810,
    0xC811,
    0xC812,
    0xC813,
    0xC814,
    0xC815,
    0xC816,
}


def get_end_code_name(end_code: int) -> str:
    """Return the stable code-derived key for an SLMP end code."""
    return f"slmp_end_code_{int(end_code) & 0xFFFF:04x}"


def get_end_code_message(end_code: int, language: SlmpEndCodeLanguage = "en") -> str | None:
    """Return a user-facing message for an SLMP end code.

    Localized message text is not embedded in this package. Resolve
    get_end_code_name(end_code) in an application-owned catalog when text is
    required.
    """
    _ = end_code
    _ = language
    return None


def is_remote_password_end_code(end_code: int) -> bool:
    """Return True if the SLMP end code is related to remote password protection."""
    return (int(end_code) & 0xFFFF) in _REMOTE_PASSWORD_END_CODES
