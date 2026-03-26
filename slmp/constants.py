"""SLMP 4E binary constants and command/device definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

FRAME_3E_REQUEST_SUBHEADER = b"\x50\x00"
FRAME_3E_RESPONSE_SUBHEADER = b"\xd0\x00"
FRAME_4E_REQUEST_SUBHEADER = b"\x54\x00"
FRAME_4E_RESPONSE_SUBHEADER = b"\xd4\x00"


class FrameType(str, Enum):
    """SLMP frame type (3E or 4E)."""

    FRAME_3E = "3e"
    FRAME_4E = "4e"


class PLCSeries(str, Enum):
    """Series option for subcommand compatibility."""

    QL = "ql"  # MELSEC-Q/L compatible (0000/0001)
    IQR = "iqr"  # MELSEC iQ-R/iQ-L (0002/0003)


class SlmpProfileClass(str, Enum):
    """Profile class identified by :func:`~slmp.core.recommend_profile`."""

    MODERN_IQR = "modern_iqr"  # iQ-R / iQ-L series
    LEGACY_QL = "legacy_ql"  # Q / L / FX5 series
    UNKNOWN = "unknown"  # Could not determine from model name/code


class DeviceUnit(IntEnum):
    """Device unit (bit or word)."""

    BIT = 0
    WORD = 1


class ModuleIONo(IntEnum):
    """Request destination module I/O No. from SH080956ENGN 4.2."""

    OWN_STATION = 0x03FF
    CONTROL_CPU = 0x03FF
    MULTIPLE_CPU_1 = 0x03E0
    MULTIPLE_CPU_2 = 0x03E1
    MULTIPLE_CPU_3 = 0x03E2
    MULTIPLE_CPU_4 = 0x03E3
    CONTROL_SYSTEM_CPU = 0x03D0
    STANDBY_SYSTEM_CPU = 0x03D1
    SYSTEM_A_CPU = 0x03D2
    SYSTEM_B_CPU = 0x03D3

    # Remote head aliases
    REMOTE_HEAD_1 = 0x03E0
    REMOTE_HEAD_2 = 0x03E1
    CONTROL_SYSTEM_REMOTE_HEAD = 0x03D0
    STANDBY_SYSTEM_REMOTE_HEAD = 0x03D1


class Command(IntEnum):
    """Command list from SH080956ENGN 5.1."""

    # Device
    DEVICE_READ = 0x0401
    DEVICE_WRITE = 0x1401
    DEVICE_READ_RANDOM = 0x0403
    DEVICE_WRITE_RANDOM = 0x1402
    DEVICE_ENTRY_MONITOR = 0x0801
    DEVICE_EXECUTE_MONITOR = 0x0802
    DEVICE_READ_BLOCK = 0x0406
    DEVICE_WRITE_BLOCK = 0x1406

    # Label
    LABEL_ARRAY_READ = 0x041A
    LABEL_ARRAY_WRITE = 0x141A
    LABEL_READ_RANDOM = 0x041C
    LABEL_WRITE_RANDOM = 0x141B

    # Memory / Extend unit
    MEMORY_READ = 0x0613
    MEMORY_WRITE = 0x1613
    EXTEND_UNIT_READ = 0x0601
    EXTEND_UNIT_WRITE = 0x1601

    # Remote control
    REMOTE_RUN = 0x1001
    REMOTE_STOP = 0x1002
    REMOTE_PAUSE = 0x1003
    REMOTE_LATCH_CLEAR = 0x1005
    REMOTE_RESET = 0x1006
    READ_TYPE_NAME = 0x0101

    # Remote password
    REMOTE_PASSWORD_LOCK = 0x1631
    REMOTE_PASSWORD_UNLOCK = 0x1630

    # Other
    SELF_TEST = 0x0619
    CLEAR_ERROR = 0x1617


SUBCOMMAND_DEVICE_WORD_QL = 0x0000
SUBCOMMAND_DEVICE_BIT_QL = 0x0001
SUBCOMMAND_DEVICE_WORD_IQR = 0x0002
SUBCOMMAND_DEVICE_BIT_IQR = 0x0003

SUBCOMMAND_DEVICE_WORD_QL_EXT = 0x0080
SUBCOMMAND_DEVICE_BIT_QL_EXT = 0x0081
SUBCOMMAND_DEVICE_WORD_IQR_EXT = 0x0082
SUBCOMMAND_DEVICE_BIT_IQR_EXT = 0x0083

# Direct memory specification (binary, Extended Device)
DIRECT_MEMORY_NORMAL = 0x00
DIRECT_MEMORY_MODULE_ACCESS = 0xF8
DIRECT_MEMORY_LINK_DIRECT = 0xF9
DIRECT_MEMORY_CPU_BUFFER = 0xFA


@dataclass(frozen=True)
class DeviceCode:
    """Device code and number radix."""

    code: int
    radix: int  # 10 or 16
    unit: DeviceUnit = DeviceUnit.WORD


# Device codes from SH080956ENGN 5.2 (binary code column).
DEVICE_CODES: dict[str, DeviceCode] = {
    "SM": DeviceCode(0x0091, 10, DeviceUnit.BIT),
    "SD": DeviceCode(0x00A9, 10, DeviceUnit.WORD),
    "X": DeviceCode(0x009C, 16, DeviceUnit.BIT),
    "Y": DeviceCode(0x009D, 16, DeviceUnit.BIT),
    "M": DeviceCode(0x0090, 10, DeviceUnit.BIT),
    "L": DeviceCode(0x0092, 10, DeviceUnit.BIT),
    "F": DeviceCode(0x0093, 10, DeviceUnit.BIT),
    "V": DeviceCode(0x0094, 10, DeviceUnit.BIT),
    "B": DeviceCode(0x00A0, 16, DeviceUnit.BIT),
    "D": DeviceCode(0x00A8, 10, DeviceUnit.WORD),
    "W": DeviceCode(0x00B4, 16, DeviceUnit.WORD),
    "TS": DeviceCode(0x00C1, 10, DeviceUnit.BIT),
    "TC": DeviceCode(0x00C0, 10, DeviceUnit.BIT),
    "TN": DeviceCode(0x00C2, 10, DeviceUnit.WORD),
    "LTS": DeviceCode(0x0051, 10, DeviceUnit.BIT),
    "LTC": DeviceCode(0x0050, 10, DeviceUnit.BIT),
    "LTN": DeviceCode(0x0052, 10, DeviceUnit.WORD),
    "STS": DeviceCode(0x00C7, 10, DeviceUnit.BIT),
    "STC": DeviceCode(0x00C6, 10, DeviceUnit.BIT),
    "STN": DeviceCode(0x00C8, 10, DeviceUnit.WORD),
    "LSTS": DeviceCode(0x0059, 10, DeviceUnit.BIT),
    "LSTC": DeviceCode(0x0058, 10, DeviceUnit.BIT),
    "LSTN": DeviceCode(0x005A, 10, DeviceUnit.WORD),
    "CS": DeviceCode(0x00C4, 10, DeviceUnit.BIT),
    "CC": DeviceCode(0x00C3, 10, DeviceUnit.BIT),
    "CN": DeviceCode(0x00C5, 10, DeviceUnit.WORD),
    "LCS": DeviceCode(0x0055, 10, DeviceUnit.BIT),
    "LCC": DeviceCode(0x0054, 10, DeviceUnit.BIT),
    "LCN": DeviceCode(0x0056, 10, DeviceUnit.WORD),
    "SB": DeviceCode(0x00A1, 16, DeviceUnit.BIT),
    "SW": DeviceCode(0x00B5, 16, DeviceUnit.WORD),
    "DX": DeviceCode(0x00A2, 16, DeviceUnit.BIT),
    "DY": DeviceCode(0x00A3, 16, DeviceUnit.BIT),
    "Z": DeviceCode(0x00CC, 10, DeviceUnit.WORD),
    "LZ": DeviceCode(0x0062, 10, DeviceUnit.WORD),
    "R": DeviceCode(0x00AF, 10, DeviceUnit.WORD),
    "ZR": DeviceCode(0x00B0, 10, DeviceUnit.WORD),
    "RD": DeviceCode(0x002C, 10, DeviceUnit.WORD),
    # Extended Device extension device codes
    "G": DeviceCode(0x00AB, 10, DeviceUnit.WORD),
    "HG": DeviceCode(0x002E, 10, DeviceUnit.WORD),
}
