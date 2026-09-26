"""
Enumerations for the values the BC246T sends and accepts.

Each member's value is the exact code used on the wire, so members can
be passed straight to the scanner and compared against its responses.
"""

from enum import IntEnum, StrEnum


class KeyCode(StrEnum):
    """
    Front-panel keys, as sent by the ``KEY`` command.
    """

    MENU = "M"
    F = "F"
    HOLD = "H"
    SCAN = "S"
    SEARCH = "S"
    LOCKOUT = "L"
    LIGHT = "!"
    LOCK = "!"
    KEY_1 = "1"
    PRI = "1"
    KEY_2 = "2"
    WX = "2"
    KEY_3 = "3"
    KEY_4 = "4"
    KEY_5 = "5"
    KEY_6 = "6"
    KEY_7 = "7"
    RCL = "7"
    KEY_8 = "8"
    KEY_9 = "9"
    KEY_0 = "0"
    DOT = "."
    NO = "."
    REV = "."
    E = "E"
    YES = "E"
    ATT = "E"
    VFO_RIGHT = ">"
    VFO_LEFT = "<"
    VFO_PUSH = "^"
    POWER = "P"


class KeyMode(StrEnum):
    """
    How a key is pressed.
    """

    PRESS = "P"
    LONG_PRESS = "L"
    HOLD = "H"
    RELEASE = "R"


class Modulation(StrEnum):
    """
    Receive modulation. ``AUTO`` uses the band's default.
    """

    AUTO = "AUTO"
    FM = "FM"
    NFM = "NFM"
    AM = "AM"


class Backlight(StrEnum):
    """
    When the display backlight comes on.
    """

    ALWAYS_ON = "IF"
    TEN_SECONDS = "10"
    THIRTY_SECONDS = "30"
    KEYPRESS = "KY"
    SQUELCH = "SQ"


class PriorityMode(IntEnum):
    """
    Priority channel checking: off, on, or Priority Plus.
    """

    OFF = 0
    ON = 1
    PLUS = 2


class SystemType(StrEnum):
    """
    Conventional or trunked system type, as ``CSY`` names it.
    """

    CONVENTIONAL = "CNV"
    MOTOROLA_800_TYPE2_STANDARD = "M82S"
    MOTOROLA_800_TYPE2_SPLINTER = "M82P"
    MOTOROLA_900_TYPE2 = "M92"
    MOTOROLA_VHF_TYPE2 = "MV2"
    MOTOROLA_UHF_TYPE2 = "MU2"
    MOTOROLA_800_TYPE1_STANDARD = "M81S"
    MOTOROLA_800_TYPE1_SPLINTER = "M81P"
    EDACS_NARROW = "EDN"
    EDACS_WIDE = "EDW"
    EDACS_SCAT = "EDS"
    LTR = "LTR"
    MOTOROLA_800_TYPE2_CUSTOM = "M82C"
    MOTOROLA_800_TYPE1_CUSTOM = "M81C"

    @property
    def is_trunked(self) -> bool:
        """
        Whether this is any trunked type.
        """
        return self is not SystemType.CONVENTIONAL


class GroupType(StrEnum):
    """
    What a group holds: channels or talkgroup IDs.
    """

    CHANNEL = "C"
    TALKGROUP = "T"


class IdMode(StrEnum):
    """
    Whether a trunked system scans stored IDs or searches for any.
    """

    SCAN = "0"
    SEARCH = "1"


class DisplayMode(StrEnum):
    """
    How a single character on the LCD is drawn.
    """

    NORMAL = " "
    REVERSE = "*"
    CURSOR = "_"
    BLINK = "#"


class IconState(StrEnum):
    """
    State of one LCD icon.
    """

    OFF = "0"
    ON = "1"
    BLINK = "2"


class CloseCallMode(StrEnum):
    """
    Close Call off, with priority, or in Do Not Disturb mode.
    """

    OFF = "0"
    PRIORITY = "1"
    DO_NOT_DISTURB = "2"


class Alert(StrEnum):
    """
    How the scanner signals a Close Call hit.
    """

    NONE = "N"
    BEEP = "B"
    LIGHT = "L"
    BEEP_AND_LIGHT = "A"


class CloseCallBand(StrEnum):
    """
    Close Call bands, in the order the ``CLC`` command lists them.
    """

    VHF_LOW = "vhf_low"
    AIR = "air"
    VHF_HIGH = "vhf_high"
    UHF = "uhf"
    BAND_800_PLUS = "800_plus"


# Valid search steps, in 10 Hz units. 0 means automatic.
SEARCH_STEPS: tuple[int, ...] = (
    0,
    500,
    625,
    750,
    1000,
    1250,
    1500,
    2000,
    2500,
    5000,
    10000,
    20000,
)
