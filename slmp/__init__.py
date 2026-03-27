"""SLMP client library with high-level helpers as the recommended user surface.

The primary user-facing entry points are:

- ``read_typed`` / ``write_typed``
- ``read_words`` / ``read_dwords``
- ``write_bit_in_word``
- ``read_named`` / ``write_named``
- ``poll``
"""

__version__ = "0.1.2"

from .async_client import AsyncSlmpClient
from .client import SlmpClient
from .constants import Command, FrameType, ModuleIONo, PLCSeries
from .core import (
    DEVICE_CODES,
    BlockReadResult,
    DeviceBlockResult,
    DeviceRef,
    ExtensionSpec,
    LabelArrayReadPoint,
    LabelArrayReadResult,
    LabelArrayWritePoint,
    LabelRandomReadResult,
    LabelRandomWritePoint,
    LongTimerResult,
    MonitorResult,
    RandomReadResult,
    SlmpResponse,
    SlmpTarget,
    SlmpTraceFrame,
    TypeNameInfo,
    parse_device,
    parse_extended_device,
)
from .errors import (
    SlmpBoundaryBehaviorWarning,
    SlmpError,
    SlmpPracticalPathWarning,
    SlmpUnsupportedDeviceError,
)
from .utils import (
    QueuedAsyncSlmpClient,
    poll,
    poll_sync,
    read_bits,
    read_bits_sync,
    read_dwords,
    read_dwords_sync,
    read_named,
    read_named_sync,
    read_typed,
    read_typed_sync,
    read_words,
    read_words_sync,
    write_bit_in_word,
    write_bit_in_word_sync,
    write_bits,
    write_bits_sync,
    write_named,
    write_named_sync,
    write_typed,
    write_typed_sync,
)

__all__ = [
    "AsyncSlmpClient",
    "BlockReadResult",
    "Command",
    "DEVICE_CODES",
    "DeviceBlockResult",
    "DeviceRef",
    "ExtensionSpec",
    "FrameType",
    "LabelArrayReadPoint",
    "LabelArrayReadResult",
    "LabelArrayWritePoint",
    "LabelRandomReadResult",
    "LabelRandomWritePoint",
    "LongTimerResult",
    "ModuleIONo",
    "MonitorResult",
    "PLCSeries",
    "QueuedAsyncSlmpClient",
    "RandomReadResult",
    "SlmpClient",
    "SlmpBoundaryBehaviorWarning",
    "SlmpError",
    "SlmpPracticalPathWarning",
    "SlmpUnsupportedDeviceError",
    "SlmpResponse",
    "SlmpTarget",
    "SlmpTraceFrame",
    "TypeNameInfo",
    "parse_extended_device",
    "parse_device",
    "poll",
    "poll_sync",
    "read_bits",
    "read_bits_sync",
    "read_dwords",
    "read_dwords_sync",
    "read_named",
    "read_named_sync",
    "read_typed",
    "read_typed_sync",
    "read_words",
    "read_words_sync",
    "write_bit_in_word",
    "write_bit_in_word_sync",
    "write_bits",
    "write_bits_sync",
    "write_named",
    "write_named_sync",
    "write_typed",
    "write_typed_sync",
]
