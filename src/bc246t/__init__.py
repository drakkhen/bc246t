"""
Remote control and programming for the Uniden Bearcat BC246T scanner.

    from bc246t import Scanner

    with Scanner.open() as scanner:
        print(scanner.get_status().line1.text)
"""

from importlib.metadata import PackageNotFoundError, version

from .enums import (
    SEARCH_STEPS,
    Alert,
    Backlight,
    CloseCallBand,
    CloseCallMode,
    DisplayMode,
    GroupType,
    IconState,
    IdMode,
    KeyCode,
    KeyMode,
    Modulation,
    PriorityMode,
    SystemType,
)
from .errors import (
    CommandError,
    CommandRejectedError,
    FramingError,
    NoFreeMemoryError,
    OverrunError,
    ScannerError,
    ScannerNotFoundError,
    ScannerTimeoutError,
    UnexpectedResponseError,
)
from .frequency import format_mhz, parse_mhz
from .models import (
    BandPlanRange,
    ChannelInfo,
    CloseCallSettings,
    CustomSearchRange,
    DisplayLine,
    GroupInfo,
    Icons,
    SameGroup,
    SearchSettings,
    Status,
    SystemInfo,
    TalkgroupInfo,
    TalkgroupStatus,
    TrunkBand,
    TrunkFrequency,
    TrunkInfo,
)
from .scanner import UNCHANGED, Scanner, find_port

try:
    __version__ = version("bc246t")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "SEARCH_STEPS",
    "UNCHANGED",
    "Alert",
    "Backlight",
    "BandPlanRange",
    "ChannelInfo",
    "CloseCallBand",
    "CloseCallMode",
    "CloseCallSettings",
    "CommandError",
    "CommandRejectedError",
    "CustomSearchRange",
    "DisplayLine",
    "DisplayMode",
    "FramingError",
    "GroupInfo",
    "GroupType",
    "IconState",
    "Icons",
    "IdMode",
    "KeyCode",
    "KeyMode",
    "Modulation",
    "NoFreeMemoryError",
    "OverrunError",
    "PriorityMode",
    "SameGroup",
    "Scanner",
    "ScannerError",
    "ScannerNotFoundError",
    "ScannerTimeoutError",
    "SearchSettings",
    "Status",
    "SystemInfo",
    "SystemType",
    "TalkgroupInfo",
    "TalkgroupStatus",
    "TrunkBand",
    "TrunkFrequency",
    "TrunkInfo",
    "UnexpectedResponseError",
    "find_port",
    "format_mhz",
    "parse_mhz",
]
