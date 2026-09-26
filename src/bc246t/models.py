"""
Records returned by :class:`bc246t.Scanner`.

Frequencies are integers in 100 Hz units (see :mod:`bc246t.frequency`).
Search steps are in 10 Hz units. Memory indexes are the scanner's own
handles; ``None`` stands for the ``-1`` the scanner uses at either end
of a chain.
"""

from dataclasses import dataclass

from .enums import (
    Alert,
    CloseCallBand,
    CloseCallMode,
    DisplayMode,
    GroupType,
    IconState,
    IdMode,
    Modulation,
    SystemType,
)


@dataclass(frozen=True, slots=True)
class DisplayLine:
    """
    One 16-character line of the LCD, and how each character is drawn.
    """

    text: str
    modes: tuple[DisplayMode, ...]


@dataclass(frozen=True, slots=True)
class Icons:
    """
    State of every icon on the LCD.

    ``system_keys`` and ``group_keys`` map quick key numbers 1-10 (the
    key labelled 0 is 10) to the state of that digit on the display.
    """

    system: IconState
    system_keys: dict[int, IconState]
    attenuation: IconState
    priority: IconState
    key_lock: IconState
    battery: IconState
    group: IconState
    group_keys: dict[int, IconState]
    am: IconState
    narrow: IconState
    fm: IconState
    lockout: IconState
    function: IconState
    close_call: IconState


@dataclass(frozen=True, slots=True)
class Status:
    """
    Everything ``STS`` reports: the LCD plus a few status flags.
    """

    line1: DisplayLine
    line2: DisplayLine
    icons: Icons
    squelch_open: bool
    muted: bool
    battery_low: bool
    weather_alert: bool
    # The SAME event code of a weather alert, when reported.
    same_event_code: str | None


@dataclass(frozen=True, slots=True)
class TalkgroupStatus:
    """
    The talkgroup currently shown on the display.
    """

    system_type: SystemType
    tgid: str
    id_mode: IdMode
    system_name: str
    group_name: str
    tgid_name: str


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """
    A stored system. Fields the system type doesn't use are ``None``.
    """

    index: int
    system_type: SystemType
    name: str
    quick_key: int | None
    hold_time: int | None
    lockout: bool
    attenuation: bool | None
    delay_time: int | None
    data_skip: bool | None
    emergency_alert: bool | None
    previous_index: int | None
    next_index: int | None
    first_group_index: int | None
    last_group_index: int | None
    sequence_number: int


@dataclass(frozen=True, slots=True)
class TrunkBand:
    """
    One base/step/offset band of a Motorola VHF or UHF system.
    """

    base: int | None
    step: int | None
    offset: int | None


@dataclass(frozen=True, slots=True)
class TrunkInfo:
    """
    Trunking settings of a system.

    Settings its type doesn't use are ``None``.
    """

    id_search: bool | None
    motorola_status_bit: bool | None
    motorola_end_code: bool | None
    edacs_afs_format: bool | None
    i_call: bool | None
    control_channel_only: bool | None
    # 0-15 for a preset fleet map, 16 for the custom one.
    fleet_map: int | None
    # Eight size codes, one hex digit (0-E) per block.
    custom_fleet_map: str | None
    bands: tuple[TrunkBand, TrunkBand, TrunkBand]
    first_talkgroup_group_index: int | None
    last_talkgroup_group_index: int | None
    first_lockout_group_index: int | None
    last_lockout_group_index: int | None


@dataclass(frozen=True, slots=True)
class TrunkFrequency:
    """
    A frequency stored in a trunked system.
    """

    index: int
    frequency: int
    lcn: int | None
    previous_index: int | None
    next_index: int | None
    system_index: int
    group_index: int


@dataclass(frozen=True, slots=True)
class GroupInfo:
    """
    A channel group or talkgroup group.
    """

    index: int
    group_type: GroupType
    name: str
    quick_key: int | None
    lockout: bool
    previous_index: int | None
    next_index: int | None
    system_index: int
    first_channel_index: int | None
    last_channel_index: int | None
    sequence_number: int


@dataclass(frozen=True, slots=True)
class ChannelInfo:
    """
    A conventional channel. ``tone`` is a code from :mod:`bc246t.tones`.
    """

    index: int
    name: str
    frequency: int
    step: int
    modulation: Modulation
    tone: int
    tone_lockout: bool
    lockout: bool
    priority: bool
    attenuation: bool
    alert: bool
    previous_index: int | None
    next_index: int | None
    system_index: int
    group_index: int


@dataclass(frozen=True, slots=True)
class TalkgroupInfo:
    """
    A talkgroup ID stored in a talkgroup group.
    """

    index: int
    name: str
    tgid: str
    lockout: bool
    alert: bool
    previous_index: int | None
    next_index: int | None
    system_index: int
    group_index: int


@dataclass(frozen=True, slots=True)
class SearchSettings:
    """
    Settings shared by Search and Close Call.
    """

    step: int
    modulation: Modulation
    attenuation: bool
    delay_time: int
    data_skip: bool
    tone_search: bool
    pager_screen: bool
    uhf_tv_screen: bool
    repeater_find: bool
    max_auto_store: int


@dataclass(frozen=True, slots=True)
class CloseCallSettings:
    """
    Close Call mode, alert and bands.
    """

    mode: CloseCallMode
    override: bool
    alert: Alert
    bands: frozenset[CloseCallBand]


@dataclass(frozen=True, slots=True)
class CustomSearchRange:
    """
    One of the ten custom search ranges.
    """

    name: str
    lower_limit: int
    upper_limit: int
    step: int
    modulation: Modulation
    attenuation: bool
    delay_time: int
    data_skip: bool


@dataclass(frozen=True, slots=True)
class SameGroup:
    """
    A weather alert SAME group: a name and up to eight FIPS codes.
    """

    name: str
    fips_codes: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class BandPlanRange:
    """
    One of the six ranges in a Motorola 800 MHz custom band plan.
    """

    lower: int | None
    upper: int | None
    step: int | None
    offset: int | None
