"""Shared command safety classification for sync and async clients."""

from __future__ import annotations

from .constants import Command

_READ_ONLY_COMMANDS = frozenset(
    {
        int(Command.DEVICE_READ),
        int(Command.DEVICE_READ_RANDOM),
        int(Command.DEVICE_EXECUTE_MONITOR),
        int(Command.DEVICE_READ_BLOCK),
        int(Command.LABEL_ARRAY_READ),
        int(Command.LABEL_READ_RANDOM),
        int(Command.MEMORY_READ),
        int(Command.EXTEND_UNIT_READ),
        int(Command.READ_TYPE_NAME),
        int(Command.SELF_TEST),
    }
)

_STATE_CHANGING_COMMANDS = frozenset(int(command) for command in Command) - _READ_ONLY_COMMANDS


def classify_command_state(command: int, override: bool | None = None) -> bool:
    """Return whether a command must use state-changing failure semantics."""
    if override is not None and type(override) is not bool:
        raise ValueError("state_changing must be a boolean or None")
    if override is False and command in _STATE_CHANGING_COMMANDS:
        raise ValueError("state_changing=False cannot downgrade a known state-changing command")
    if override is not None:
        return override
    return command not in _READ_ONLY_COMMANDS
