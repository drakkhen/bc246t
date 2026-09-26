"""
Serial interface to the Uniden BC246T.

Each method wraps one remote command from Uniden's "BC246T PC Protocol"
document (V2.60). Commands marked *program mode* in their docstring are
refused with :class:`~bc246t.errors.CommandRejectedError` unless the
scanner is in program mode; see :meth:`Scanner.program_mode`.
"""

from __future__ import annotations

import enum
import logging
import re
from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Final, Literal, Protocol, TypeVar

import serial
from serial.tools import list_ports

from .enums import (
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
    ScannerNotFoundError,
    ScannerTimeoutError,
    UnexpectedResponseError,
)
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

log = logging.getLogger(__name__)

DEFAULT_BAUDRATE: Final = 57600
DEFAULT_TIMEOUT: Final = 2.0
# The spec says ``CLR`` takes about 10 seconds.
CLEAR_MEMORY_TIMEOUT: Final = 20.0
# USB vendor of the PL2303 chip in Uniden's USB-1 cable.
PROLIFIC_VENDOR_ID: Final = 0x067B

NAME_MAX_LENGTH: Final = 16
_LINE_WIDTH: Final = 16
_PADDED_DISPLAY: Final = re.compile(",".join([f"(.{{{_LINE_WIDTH}}})"] * 4 + ["(.*)"]), re.DOTALL)
_ERROR_RESPONSES: Final = {
    "ERR": CommandError,
    "NG": CommandRejectedError,
    "FER": FramingError,
    "ORER": OverrunError,
}


class _Unchanged(enum.Enum):
    UNCHANGED = "UNCHANGED"

    def __repr__(self) -> str:
        return "UNCHANGED"


# Default for setter arguments. It sends an empty field, which the
# scanner leaves as it is.
UNCHANGED: Final = _Unchanged.UNCHANGED

T = TypeVar("T")
Keep = Literal[_Unchanged.UNCHANGED]


class Transport(Protocol):
    """
    The part of :class:`serial.Serial` the scanner needs.
    """

    @property
    def timeout(self) -> float | None:
        """
        Read timeout in seconds, or ``None`` to wait forever.
        """
        ...

    @timeout.setter
    def timeout(self, timeout: float | None) -> None: ...

    def write(self, data: bytes, /) -> int | None:
        """
        Send raw bytes.
        """
        ...

    def read_until(self, expected: bytes = ..., size: int | None = ...) -> bytes:
        """
        Read up to and including ``expected``, or until the timeout.
        """
        ...

    def close(self) -> None:
        """
        Close the port.
        """
        ...


def find_port() -> str:
    """
    Return the port of the one attached Prolific USB-serial adapter.

    Raises :class:`ScannerNotFoundError` when there are none or
    several.
    """
    ports = sorted(p.device for p in list_ports.comports() if p.vid == PROLIFIC_VENDOR_ID)
    if len(ports) == 1:
        return ports[0]
    if not ports:
        raise ScannerNotFoundError("no Prolific USB-serial adapter found; pass a port")
    raise ScannerNotFoundError(f"several Prolific adapters found, pick one: {', '.join(ports)}")


# Encoding and decoding of single fields.


def _encode(value: object) -> str:
    if value is UNCHANGED or value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def _encode_frequency(value: int | Keep) -> str:
    return "" if value is UNCHANGED else f"{int(value):08d}"


def _encode_quick_key(value: int | Keep | None) -> str:
    if value is UNCHANGED:
        return ""
    if value is None:
        return "."
    _check_key(value)
    return str(value % 10)


def _encode_name(value: str | Keep) -> str:
    if value is UNCHANGED:
        return ""
    if len(value) > NAME_MAX_LENGTH:
        raise ValueError(f"name longer than {NAME_MAX_LENGTH} characters: {value!r}")
    if "," in value or "\r" in value:
        raise ValueError(f"name can't contain a comma or carriage return: {value!r}")
    return value


def _encode_key_set(keys: Iterable[int], *, on: str = "1", off: str = "0") -> str:
    """
    Encode quick keys 1-10 as ten digits, as QSL, QGL and CSG use.
    """
    keys = set(keys)
    for key in keys:
        _check_key(key)
    return "".join(on if key in keys else off for key in range(1, 11))


def _decode_key_set(bits: str, *, on: str = "1") -> set[int]:
    if len(bits) != 10 or set(bits) - {"0", "1"}:
        raise UnexpectedResponseError(f"expected ten 0/1 digits, got {bits!r}")
    return {key for key, bit in zip(range(1, 11), bits, strict=True) if bit == on}


def _check_key(key: int) -> None:
    if not 1 <= key <= 10:
        raise ValueError(f"quick keys run from 1 to 10, got {key}")


def _flag(value: str) -> bool | None:
    if value == "":
        return None
    if value in ("0", "1"):
        return value == "1"
    raise UnexpectedResponseError(f"expected 0 or 1, got {value!r}")


def _require(value: T | None) -> T:
    if value is None:
        raise UnexpectedResponseError("a required field was empty")
    return value


def _int(value: str) -> int | None:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        raise UnexpectedResponseError(f"expected a number, got {value!r}") from None


def _index(value: str) -> int | None:
    number = _int(value)
    return None if number == -1 else number


def _quick_key(value: str) -> int | None:
    if value in ("", "."):
        return None
    number = _require(_int(value))
    return number or 10


def _enum(kind: Callable[[Any], T], value: str | int) -> T:
    try:
        return kind(value)
    except ValueError:
        raise UnexpectedResponseError(
            f"unexpected {getattr(kind, '__name__', kind)}: {value!r}"
        ) from None


class Scanner:
    """
    A BC246T on a serial port.

    Open one with :meth:`open`, or pass anything that behaves like
    :class:`serial.Serial` to the constructor. Use it as a context
    manager to close the port when you're done::

        with Scanner.open() as scanner:
            print(scanner.get_model(), scanner.get_firmware_version())
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    @classmethod
    def open(
        cls,
        port: str | None = None,
        *,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Scanner:
        """
        Open the scanner on ``port``, or on one :func:`find_port` picks.

        ``baudrate`` must match the scanner's PC Control setting.
        """
        return cls(serial.Serial(port or find_port(), baudrate=baudrate, timeout=timeout))

    def close(self) -> None:
        """
        Close the port.
        """
        self._transport.close()

    def __enter__(self) -> Scanner:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # Low-level exchange.

    def _exchange(self, line: str, timeout: float | None = None) -> str:
        log.debug("send %r", line)
        saved_timeout = self._transport.timeout
        if timeout is not None:
            self._transport.timeout = timeout
        try:
            self._transport.write(f"{line}\r".encode("latin-1"))
            raw = self._transport.read_until(b"\r")
        finally:
            self._transport.timeout = saved_timeout
        if not raw.endswith(b"\r"):
            raise ScannerTimeoutError(f"no complete response to {line.split(',')[0]}")
        response = raw[:-1].decode("latin-1")
        log.debug("recv %r", response)
        return response

    def _command(self, command: str, *args: str, timeout: float | None = None) -> list[str]:
        """
        Send pre-encoded arguments and return the response fields.
        """
        response = self._exchange(",".join((command, *args)), timeout)
        fields = response.split(",")
        _raise_for_error(command, fields)
        if fields[0] != command:
            raise UnexpectedResponseError(f"expected a {command} response, got {response!r}")
        return fields[1:]

    def _query(self, command: str, *args: str, count: int = 1) -> list[str]:
        """
        Send a command and return exactly ``count`` response fields.
        """
        fields = self._command(command, *args)
        # Some responses (CIN, for one) end with a stray comma.
        if len(fields) == count + 1 and fields[-1] == "":
            fields.pop()
        if len(fields) != count:
            raise UnexpectedResponseError(
                f"{command} returned {len(fields)} fields, expected {count}: {fields!r}"
            )
        return fields

    def _set(self, command: str, *args: str, timeout: float | None = None) -> None:
        """
        Send a command that answers ``OK``.
        """
        fields = self._command(command, *args, timeout=timeout)
        if fields != ["OK"]:
            raise UnexpectedResponseError(f"expected {command},OK, got {fields!r}")

    def _new_index(self, command: str, parent_index: int) -> int:
        (value,) = self._query(command, str(parent_index))
        index = _index(value)
        if index is None:
            raise NoFreeMemoryError
        return index

    # Remote control.

    def get_current_talkgroup(self) -> TalkgroupStatus | None:
        """
        Return the talkgroup on the display, or ``None``.
        """
        fields = self._query("GID", count=6)
        if not any(fields):
            return None
        system_type, tgid, id_mode, system_name, group_name, tgid_name = fields
        return TalkgroupStatus(
            system_type=_enum(SystemType, system_type),
            tgid=tgid,
            id_mode=_enum(IdMode, id_mode),
            system_name=system_name,
            group_name=group_name,
            tgid_name=tgid_name,
        )

    def press_key(self, key: KeyCode, mode: KeyMode = KeyMode.PRESS) -> None:
        """
        Press a front-panel key.

        Hold one key with ``KeyMode.HOLD``, press another, then release
        the first with ``KeyMode.RELEASE`` to send a combination such as
        F + SCAN. The VFO knob only takes ``KeyMode.PRESS``.
        ``KeyCode.POWER`` can't turn the scanner off; use
        :meth:`power_off`.
        """
        key, mode = KeyCode(key), KeyMode(mode)
        if key in (KeyCode.VFO_LEFT, KeyCode.VFO_RIGHT) and mode is not KeyMode.PRESS:
            raise ValueError("turning the VFO knob only works with KeyMode.PRESS")
        self._set("KEY", key.value, mode.value)

    def power_off(self) -> None:
        """
        Turn the scanner off. It ignores every command after this one.
        """
        self._set("POF")

    def tune(
        self,
        frequency: int,
        *,
        step: int | Keep = UNCHANGED,
        modulation: Modulation | Keep = UNCHANGED,
        attenuation: bool | Keep = UNCHANGED,
        delay_time: int | Keep = UNCHANGED,
        data_skip: bool | Keep = UNCHANGED,
        tone_search: bool | Keep = UNCHANGED,
        pager_screen: bool | Keep = UNCHANGED,
        uhf_tv_screen: bool | Keep = UNCHANGED,
        repeater_find: bool | Keep = UNCHANGED,
    ) -> None:
        """
        Go to Quick Search Hold on ``frequency``.

        The other arguments change the Search/Close Call options, the
        same ones :meth:`set_search_settings` sets. Refused while the
        scanner is in a menu, in direct entry, or saving a quick search.
        """
        self._set(
            "QSH",
            _encode_frequency(frequency),
            _encode(step),
            _encode(modulation),
            _encode(attenuation),
            _encode(delay_time),
            _encode(data_skip),
            _encode(tone_search),
            self._encode_screen(pager_screen, uhf_tv_screen),
            _encode(repeater_find),
        )

    def get_status(self) -> Status:
        """
        Return the LCD contents and the squelch, mute and alert flags.
        """
        response = self._exchange("STS")
        fields = response.split(",")
        _raise_for_error("STS", fields)
        if fields[0] != "STS":
            raise UnexpectedResponseError(f"expected an STS response, got {response!r}")
        line1, modes1, line2, modes2, rest = _split_display(response.removeprefix("STS,"))
        if len(rest) != 7:
            raise UnexpectedResponseError(f"STS returned an unexpected layout: {response!r}")
        icons1, icons2, _reserved, squelch, mute, battery, weather = rest
        return Status(
            line1=_display_line(line1, modes1),
            line2=_display_line(line2, modes2),
            icons=_icons(icons1, icons2),
            squelch_open=squelch == "1",
            muted=mute == "1",
            battery_low=battery == "1",
            weather_alert=weather not in ("", "0"),
            same_event_code=weather if weather not in ("", "0", "1") else None,
        )

    # System information.

    def get_model(self) -> str:
        """
        Return the model name, ``BC246T``.
        """
        (model,) = self._query("MDL")
        return model

    def get_firmware_version(self) -> str:
        """
        Return the firmware version, such as ``VR2.60``.
        """
        (version,) = self._query("VER")
        return version

    # Program mode.

    def enter_program_mode(self) -> None:
        """
        Enter program mode.

        The scanner shows "Remote Mode" and "Keypad Lock" and stops
        scanning until :meth:`exit_program_mode`. Refused while the
        scanner is in a menu, in direct entry, or saving a quick search.
        """
        self._set("PRG")

    def exit_program_mode(self) -> None:
        """
        Leave program mode. The scanner goes to Scan Hold.
        """
        self._set("EPG")

    @contextmanager
    def program_mode(self) -> Generator[Scanner]:
        """
        Hold the scanner in program mode for a ``with`` block.
        """
        self.enter_program_mode()
        try:
            yield self
        finally:
            self.exit_program_mode()

    # System settings (program mode).

    def get_backlight(self) -> Backlight:
        """
        Return when the backlight comes on.
        """
        (value,) = self._query("BLT")
        return _enum(Backlight, value)

    def set_backlight(self, backlight: Backlight) -> None:
        """
        Set when the backlight comes on.
        """
        self._set("BLT", Backlight(backlight).value)

    def get_battery_save(self) -> bool:
        """
        Return whether battery save is on.
        """
        (value,) = self._query("BSV")
        return _require(_flag(value))

    def set_battery_save(self, enabled: bool) -> None:
        """
        Switch battery save on or off.
        """
        self._set("BSV", _encode(bool(enabled)))

    def clear_memory(self) -> None:
        """
        Reset every setting and delete all programming.

        The baud rate is kept. Takes about ten seconds.
        """
        self._set("CLR", timeout=CLEAR_MEMORY_TIMEOUT)

    def get_key_beep(self) -> bool:
        """
        Return whether key beeps are on.
        """
        (value,) = self._query("KBP")
        return _require(_flag(value))

    def set_key_beep(self, enabled: bool) -> None:
        """
        Switch key beeps on or off.
        """
        self._set("KBP", _encode(bool(enabled)))

    def get_opening_message(self) -> tuple[str, str]:
        """
        Return the two lines shown at power-on.
        """
        line1, line2 = self._query("OMS", count=2)
        return line1, line2

    def set_opening_message(self, line1: str, line2: str = "") -> None:
        """
        Set the power-on message, up to 16 characters a line.

        A line of only spaces restores the default message.
        """
        self._set("OMS", _encode_name(line1), _encode_name(line2))

    def get_priority_mode(self) -> PriorityMode:
        """
        Return the priority mode.
        """
        (value,) = self._query("PRI")
        return _enum(PriorityMode, _require(_int(value)))

    def set_priority_mode(self, mode: PriorityMode) -> None:
        """
        Set the priority mode.
        """
        self._set("PRI", _encode(PriorityMode(mode)))

    # Systems (program mode).

    def get_system_count(self) -> int:
        """
        Return the number of stored systems, 0-200.
        """
        (value,) = self._query("SCT")
        return _require(_int(value))

    def get_first_system_index(self) -> int | None:
        """
        Return the index of the first system, or ``None``.
        """
        (value,) = self._query("SIH")
        return _index(value)

    def get_last_system_index(self) -> int | None:
        """
        Return the index of the last system, or ``None``.
        """
        (value,) = self._query("SIT")
        return _index(value)

    def get_system_quick_keys(self) -> set[int]:
        """
        Return the system quick keys (1-10) switched on for scanning.
        """
        (bits,) = self._query("QSL")
        return _decode_key_set(bits)

    def set_system_quick_keys(self, keys: Iterable[int]) -> None:
        """
        Switch on only the given system quick keys (1-10).

        The scanner ignores keys that have no system assigned.
        """
        self._set("QSL", _encode_key_set(keys))

    def get_group_quick_keys(self, system_index: int) -> set[int]:
        """
        Return the group quick keys (1-10) of a system that are on.
        """
        # The spec shows a trailing comma on this query.
        (bits,) = self._query("QGL", str(system_index), "")
        return _decode_key_set(bits)

    def set_group_quick_keys(self, system_index: int, keys: Iterable[int]) -> None:
        """
        Switch on only the given group quick keys (1-10) of a system.
        """
        self._set("QGL", str(system_index), _encode_key_set(keys))

    def create_system(self, system_type: SystemType) -> int:
        """
        Create an empty system and return its index.
        """
        (value,) = self._query("CSY", SystemType(system_type).value)
        index = _index(value)
        if index is None:
            raise NoFreeMemoryError
        return index

    def delete_system(self, system_index: int) -> None:
        """
        Delete a system and everything in it.
        """
        self._set("DSY", str(system_index))

    def copy_system(self, system_index: int, name: str) -> int:
        """
        Copy a system under a new name and return the copy's index.

        Raises :class:`CommandError` if there isn't room for the copy.
        """
        (value,) = self._query("CPS", str(system_index), _encode_name(name))
        return _require(_index(value))

    def get_system_info(self, system_index: int) -> SystemInfo:
        """
        Return a system's settings and chain indexes.
        """
        fields = self._query("SIN", str(system_index), count=14)
        (system_type, name, quick_key, hold, lockout, att, delay, skip, emergency,
         previous, following, first_group, last_group, sequence) = fields  # fmt: skip
        return SystemInfo(
            index=system_index,
            system_type=_enum(SystemType, system_type),
            name=name,
            quick_key=_quick_key(quick_key),
            hold_time=_int(hold),
            lockout=bool(_flag(lockout)),
            attenuation=_flag(att),
            delay_time=_int(delay),
            data_skip=_flag(skip),
            emergency_alert=_flag(emergency),
            previous_index=_index(previous),
            next_index=_index(following),
            first_group_index=_index(first_group),
            last_group_index=_index(last_group),
            sequence_number=_require(_int(sequence)),
        )

    def set_system_info(
        self,
        system_index: int,
        *,
        name: str | Keep = UNCHANGED,
        quick_key: int | Keep | None = UNCHANGED,
        hold_time: int | Keep = UNCHANGED,
        lockout: bool | Keep = UNCHANGED,
        attenuation: bool | Keep = UNCHANGED,
        delay_time: int | Keep = UNCHANGED,
        data_skip: bool | Keep = UNCHANGED,
        emergency_alert: bool | Keep = UNCHANGED,
    ) -> None:
        """
        Change a system's settings. Arguments left out stay as they are.

        ``quick_key`` is 1-10, or ``None`` for no quick key.
        ``hold_time`` is 0-255 seconds and ``delay_time`` 0-5 seconds.
        The scanner ignores settings the system type doesn't use.
        """
        self._set(
            "SIN",
            str(system_index),
            _encode_name(name),
            _encode_quick_key(quick_key),
            _encode(hold_time),
            _encode(lockout),
            _encode(attenuation),
            _encode(delay_time),
            _encode(data_skip),
            _encode(emergency_alert),
        )

    def get_trunk_info(self, system_index: int) -> TrunkInfo:
        """
        Return a trunked system's trunking settings.
        """
        fields = self._query("TRN", str(system_index), count=21)
        (id_search, status_bit, end_code, afs, i_call, control_only, fleet_map,
         custom_fleet_map) = fields[:8]  # fmt: skip
        band_fields = fields[8:17]
        first_tg, last_tg, first_lockout, last_lockout = fields[17:]
        bands = tuple(
            TrunkBand(base=_int(base), step=_int(step), offset=_int(offset))
            for base, step, offset in zip(*[iter(band_fields)] * 3, strict=True)
        )
        return TrunkInfo(
            id_search=_flag(id_search),
            motorola_status_bit=_flag(status_bit),
            motorola_end_code=_flag(end_code),
            edacs_afs_format=_flag(afs),
            i_call=_flag(i_call),
            control_channel_only=_flag(control_only),
            fleet_map=_int(fleet_map),
            custom_fleet_map=custom_fleet_map or None,
            bands=bands,  # type: ignore[arg-type]
            first_talkgroup_group_index=_index(first_tg),
            last_talkgroup_group_index=_index(last_tg),
            first_lockout_group_index=_index(first_lockout),
            last_lockout_group_index=_index(last_lockout),
        )

    def set_trunk_info(
        self,
        system_index: int,
        *,
        id_search: bool | Keep = UNCHANGED,
        motorola_status_bit: bool | Keep = UNCHANGED,
        motorola_end_code: bool | Keep = UNCHANGED,
        edacs_afs_format: bool | Keep = UNCHANGED,
        i_call: bool | Keep = UNCHANGED,
        control_channel_only: bool | Keep = UNCHANGED,
        fleet_map: int | Keep = UNCHANGED,
        custom_fleet_map: str | Keep = UNCHANGED,
        bands: Sequence[TrunkBand | None] | Keep = UNCHANGED,
    ) -> None:
        """
        Change a trunked system's settings.

        Arguments left out stay as they are. ``bands`` holds up to three
        base/step/offset entries, used only by Motorola VHF and UHF
        systems. A ``None`` entry or field is left as is.
        """
        band_list = [] if bands is UNCHANGED else list(bands)
        if len(band_list) > 3:
            raise ValueError("a trunked system has at most three bands")
        band_list += [None] * (3 - len(band_list))
        band_fields = []
        for band in band_list:
            band = band or TrunkBand(None, None, None)
            band_fields += [
                "" if band.base is None else _encode_frequency(band.base),
                _encode(band.step),
                _encode(band.offset),
            ]
        self._set(
            "TRN",
            str(system_index),
            _encode(id_search),
            _encode(motorola_status_bit),
            _encode(motorola_end_code),
            _encode(edacs_afs_format),
            _encode(i_call),
            _encode(control_channel_only),
            _encode(fleet_map),
            _encode(custom_fleet_map),
            *band_fields,
        )

    def get_trunk_frequency(self, index: int) -> TrunkFrequency:
        """
        Return a frequency stored in a trunked system.
        """
        fields = self._query("TFQ", str(index), count=6)
        frequency, lcn, previous, following, system_index, group_index = fields
        return TrunkFrequency(
            index=index,
            frequency=_require(_int(frequency)),
            lcn=_int(lcn),
            previous_index=_index(previous),
            next_index=_index(following),
            system_index=_require(_index(system_index)),
            group_index=_require(_index(group_index)),
        )

    def set_trunk_frequency(
        self,
        index: int,
        *,
        frequency: int | Keep = UNCHANGED,
        lcn: int | Keep = UNCHANGED,
    ) -> None:
        """
        Change a trunked system frequency.

        Motorola and EDACS SCAT systems ignore ``lcn``.
        """
        self._set("TFQ", str(index), _encode_frequency(frequency), _encode(lcn))

    # Groups (program mode).

    def append_channel_group(self, system_index: int) -> int:
        """
        Add a channel group to the end of a system and return its index.
        """
        return self._new_index("AGC", system_index)

    def append_talkgroup_group(self, system_index: int) -> int:
        """
        Add a talkgroup group to a system and return its index.
        """
        return self._new_index("AGT", system_index)

    def delete_group(self, group_index: int) -> None:
        """
        Delete a channel group or talkgroup group.
        """
        self._set("DGR", str(group_index))

    def get_group_info(self, group_index: int) -> GroupInfo:
        """
        Return a group's settings and chain indexes.
        """
        fields = self._query("GIN", str(group_index), count=10)
        (group_type, name, quick_key, lockout, previous, following, system_index,
         first_channel, last_channel, sequence) = fields  # fmt: skip
        return GroupInfo(
            index=group_index,
            group_type=_enum(GroupType, group_type),
            name=name,
            quick_key=_quick_key(quick_key),
            lockout=bool(_flag(lockout)),
            previous_index=_index(previous),
            next_index=_index(following),
            system_index=_require(_index(system_index)),
            first_channel_index=_index(first_channel),
            last_channel_index=_index(last_channel),
            sequence_number=_require(_int(sequence)),
        )

    def set_group_info(
        self,
        group_index: int,
        *,
        name: str | Keep = UNCHANGED,
        quick_key: int | Keep | None = UNCHANGED,
        lockout: bool | Keep = UNCHANGED,
    ) -> None:
        """
        Change a group's settings.

        ``quick_key`` is 1-10, or ``None`` for none. Arguments left out
        stay as they are.
        """
        self._set(
            "GIN",
            str(group_index),
            _encode_name(name),
            _encode_quick_key(quick_key),
            _encode(lockout),
        )

    # Channels and talkgroups (program mode).

    def append_channel(self, group_index: int) -> int:
        """
        Add a channel to a channel group and return its index.
        """
        return self._new_index("ACC", group_index)

    def append_talkgroup(self, group_index: int) -> int:
        """
        Add a talkgroup to a talkgroup group and return its index.
        """
        return self._new_index("ACT", group_index)

    def delete_channel(self, index: int) -> None:
        """
        Delete a channel, a talkgroup, or a trunked system frequency.
        """
        self._set("DCH", str(index))

    def get_channel_info(self, channel_index: int) -> ChannelInfo:
        """
        Return a conventional channel.
        """
        fields = self._query("CIN", str(channel_index), count=14)
        (name, frequency, step, modulation, tone, tone_lockout, lockout, priority, att,
         alert, previous, following, system_index, group_index) = fields  # fmt: skip
        return ChannelInfo(
            index=channel_index,
            name=name,
            frequency=_require(_int(frequency)),
            step=_int(step) or 0,
            modulation=_enum(Modulation, modulation),
            tone=_int(tone) or 0,
            tone_lockout=bool(_flag(tone_lockout)),
            lockout=bool(_flag(lockout)),
            priority=bool(_flag(priority)),
            attenuation=bool(_flag(att)),
            alert=bool(_flag(alert)),
            previous_index=_index(previous),
            next_index=_index(following),
            system_index=_require(_index(system_index)),
            group_index=_require(_index(group_index)),
        )

    def set_channel_info(
        self,
        channel_index: int,
        *,
        name: str | Keep = UNCHANGED,
        frequency: int | Keep = UNCHANGED,
        step: int | Keep = UNCHANGED,
        modulation: Modulation | Keep = UNCHANGED,
        tone: int | Keep = UNCHANGED,
        tone_lockout: bool | Keep = UNCHANGED,
        lockout: bool | Keep = UNCHANGED,
        priority: bool | Keep = UNCHANGED,
        attenuation: bool | Keep = UNCHANGED,
        alert: bool | Keep = UNCHANGED,
    ) -> None:
        """
        Change a channel. Arguments left out stay as they are.

        ``tone`` is a CTCSS/DCS code from :mod:`bc246t.tones`.
        """
        self._set(
            "CIN",
            str(channel_index),
            _encode_name(name),
            _encode_frequency(frequency),
            _encode(step),
            _encode(modulation),
            _encode(tone),
            _encode(tone_lockout),
            _encode(lockout),
            _encode(priority),
            _encode(attenuation),
            _encode(alert),
        )

    def get_talkgroup_info(self, talkgroup_index: int) -> TalkgroupInfo:
        """
        Return a stored talkgroup.
        """
        fields = self._query("TIN", str(talkgroup_index), count=8)
        name, tgid, lockout, alert, previous, following, system_index, group_index = fields
        return TalkgroupInfo(
            index=talkgroup_index,
            name=name,
            tgid=tgid,
            lockout=bool(_flag(lockout)),
            alert=bool(_flag(alert)),
            previous_index=_index(previous),
            next_index=_index(following),
            system_index=_require(_index(system_index)),
            group_index=_require(_index(group_index)),
        )

    def set_talkgroup_info(
        self,
        talkgroup_index: int,
        *,
        name: str | Keep = UNCHANGED,
        tgid: str | Keep = UNCHANGED,
        lockout: bool | Keep = UNCHANGED,
        alert: bool | Keep = UNCHANGED,
    ) -> None:
        """
        Change a talkgroup.

        ``tgid`` is in the format of the system's type. Arguments left
        out stay as they are.
        """
        self._set(
            "TIN",
            str(talkgroup_index),
            _encode_name(name),
            _encode(tgid),
            _encode(lockout),
            _encode(alert),
        )

    def iter_locked_out_talkgroups(self, system_index: int) -> Iterator[str]:
        """
        Yield each talkgroup ID locked out in a system.
        """
        while True:
            (tgid,) = self._query("GLI", str(system_index))
            if tgid == "-1":
                return
            yield tgid

    def unlock_talkgroup(self, system_index: int, tgid: str) -> None:
        """
        Remove a talkgroup ID from a system's lockout list.
        """
        self._set("ULI", str(system_index), tgid)

    def lock_out_talkgroup(self, system_index: int, tgid: str) -> None:
        """
        Add a talkgroup ID to a system's lockout list.
        """
        self._set("LOI", str(system_index), tgid)

    # Memory chain (program mode).

    def get_previous_index(self, index: int) -> int | None:
        """
        Return the index before ``index``, or ``None`` at the start.
        """
        (value,) = self._query("REV", str(index))
        return _index(value)

    def get_next_index(self, index: int) -> int | None:
        """
        Return the index after ``index``, or ``None`` at the end.
        """
        (value,) = self._query("FWD", str(index))
        return _index(value)

    def get_free_memory_blocks(self) -> int:
        """
        Return how many memory blocks are free, 0-9999.
        """
        (value,) = self._query("RMB")
        return _require(_int(value))

    def get_memory_used_percent(self) -> int:
        """
        Return the share of memory in use, 0-100.
        """
        (value,) = self._query("MEM")
        return _require(_int(value))

    def iter_systems(self) -> Iterator[SystemInfo]:
        """
        Yield every stored system in scan order.
        """
        index = self.get_first_system_index()
        while index is not None:
            system = self.get_system_info(index)
            yield system
            index = system.next_index

    def iter_groups(self, system: SystemInfo) -> Iterator[GroupInfo]:
        """
        Yield every group of a system in order.
        """
        index = system.first_group_index
        while index is not None:
            group = self.get_group_info(index)
            yield group
            index = group.next_index

    def iter_channels(self, group: GroupInfo) -> Iterator[ChannelInfo]:
        """
        Yield every channel of a channel group in order.
        """
        index = group.first_channel_index
        while index is not None:
            channel = self.get_channel_info(index)
            yield channel
            index = channel.next_index

    def iter_talkgroups(self, group: GroupInfo) -> Iterator[TalkgroupInfo]:
        """
        Yield every talkgroup of a talkgroup group in order.
        """
        index = group.first_channel_index
        while index is not None:
            talkgroup = self.get_talkgroup_info(index)
            yield talkgroup
            index = talkgroup.next_index

    # Search and Close Call (program mode).

    def get_search_settings(self) -> SearchSettings:
        """
        Return the settings shared by Search and Close Call.
        """
        fields = self._query("SCO", count=9)
        step, modulation, att, delay, skip, tone_search, screen, repeater, max_store = fields
        pager, uhf_tv = _decode_screen(screen)
        return SearchSettings(
            step=_require(_int(step)),
            modulation=_enum(Modulation, modulation),
            attenuation=bool(_flag(att)),
            delay_time=_require(_int(delay)),
            data_skip=bool(_flag(skip)),
            tone_search=bool(_flag(tone_search)),
            pager_screen=pager,
            uhf_tv_screen=uhf_tv,
            repeater_find=bool(_flag(repeater)),
            max_auto_store=_require(_int(max_store)),
        )

    def set_search_settings(
        self,
        *,
        step: int | Keep = UNCHANGED,
        modulation: Modulation | Keep = UNCHANGED,
        attenuation: bool | Keep = UNCHANGED,
        delay_time: int | Keep = UNCHANGED,
        data_skip: bool | Keep = UNCHANGED,
        tone_search: bool | Keep = UNCHANGED,
        pager_screen: bool | Keep = UNCHANGED,
        uhf_tv_screen: bool | Keep = UNCHANGED,
        repeater_find: bool | Keep = UNCHANGED,
        max_auto_store: int | Keep = UNCHANGED,
    ) -> None:
        """
        Change the Search/Close Call settings.

        Arguments left out stay as they are. ``max_auto_store`` is
        1-256.
        """
        self._set(
            "SCO",
            _encode(step),
            _encode(modulation),
            _encode(attenuation),
            _encode(delay_time),
            _encode(data_skip),
            _encode(tone_search),
            self._encode_screen(pager_screen, uhf_tv_screen),
            _encode(repeater_find),
            _encode(max_auto_store),
        )

    def _encode_screen(self, pager: bool | Keep, uhf_tv: bool | Keep) -> str:
        """
        Encode the pager and UHF TV screens, which share one field.

        When only one is given, the other is read back from the scanner
        first.
        """
        if pager is UNCHANGED and uhf_tv is UNCHANGED:
            return ""
        if pager is UNCHANGED or uhf_tv is UNCHANGED:
            current = self.get_search_settings()
            pager = current.pager_screen if pager is UNCHANGED else pager
            uhf_tv = current.uhf_tv_screen if uhf_tv is UNCHANGED else uhf_tv
        return f"{_encode(bool(pager))}{_encode(bool(uhf_tv))}000000"

    def iter_global_lockouts(self) -> Iterator[int]:
        """
        Yield every globally locked-out frequency.
        """
        while True:
            (value,) = self._query("GLF")
            if value == "-1":
                return
            yield _require(_int(value))

    def unlock_frequency(self, frequency: int) -> None:
        """
        Remove a frequency from the global lockout list.
        """
        self._set("ULF", _encode_frequency(frequency))

    def lock_out_frequency(self, frequency: int) -> None:
        """
        Add a frequency to the global lockout list.
        """
        self._set("LOF", _encode_frequency(frequency))

    def get_close_call_settings(self) -> CloseCallSettings:
        """
        Return the Close Call mode, alert and bands.
        """
        mode, override, alert, bands = self._query("CLC", count=4)
        if len(bands) != len(CloseCallBand) or set(bands) - {"0", "1"}:
            raise UnexpectedResponseError(f"unexpected Close Call bands: {bands!r}")
        return CloseCallSettings(
            mode=_enum(CloseCallMode, mode),
            override=bool(_flag(override)),
            alert=_enum(Alert, alert),
            bands=frozenset(
                band for band, bit in zip(CloseCallBand, bands, strict=True) if bit == "1"
            ),
        )

    def set_close_call_settings(
        self,
        *,
        mode: CloseCallMode | Keep = UNCHANGED,
        override: bool | Keep = UNCHANGED,
        alert: Alert | Keep = UNCHANGED,
        bands: Iterable[CloseCallBand] | Keep = UNCHANGED,
    ) -> None:
        """
        Change the Close Call settings.

        ``bands`` lists the bands to switch on. Arguments left out stay
        as they are.
        """
        band_bits = ""
        if bands is not UNCHANGED:
            selected = {CloseCallBand(band) for band in bands}
            band_bits = "".join("1" if band in selected else "0" for band in CloseCallBand)
        self._set("CLC", _encode(mode), _encode(override), _encode(alert), band_bits)

    # Custom search (program mode).

    def get_custom_search_ranges(self) -> set[int]:
        """
        Return the custom search ranges (1-10) that are switched on.
        """
        (bits,) = self._query("CSG")
        # In CSG a 0 marks a range as valid, the reverse of QSL and QGL.
        return _decode_key_set(bits, on="0")

    def set_custom_search_ranges(self, ranges: Iterable[int]) -> None:
        """
        Switch on only the given custom search ranges (1-10).
        """
        self._set("CSG", _encode_key_set(ranges, on="0", off="1"))

    def get_custom_search_range(self, range_number: int) -> CustomSearchRange:
        """
        Return the settings of custom search range 1-10.
        """
        _check_key(range_number)
        fields = self._query("CSP", str(range_number % 10), count=8)
        name, lower, upper, step, modulation, att, delay, skip = fields
        return CustomSearchRange(
            name=name,
            lower_limit=_require(_int(lower)),
            upper_limit=_require(_int(upper)),
            step=_require(_int(step)),
            modulation=_enum(Modulation, modulation),
            attenuation=bool(_flag(att)),
            delay_time=_require(_int(delay)),
            data_skip=bool(_flag(skip)),
        )

    def set_custom_search_range(
        self,
        range_number: int,
        *,
        name: str | Keep = UNCHANGED,
        lower_limit: int | Keep = UNCHANGED,
        upper_limit: int | Keep = UNCHANGED,
        step: int | Keep = UNCHANGED,
        modulation: Modulation | Keep = UNCHANGED,
        attenuation: bool | Keep = UNCHANGED,
        delay_time: int | Keep = UNCHANGED,
        data_skip: bool | Keep = UNCHANGED,
    ) -> None:
        """
        Change custom search range 1-10.

        Arguments left out stay as they are.
        """
        _check_key(range_number)
        self._set(
            "CSP",
            str(range_number % 10),
            _encode_name(name),
            _encode_frequency(lower_limit),
            _encode_frequency(upper_limit),
            _encode(step),
            _encode(modulation),
            _encode(attenuation),
            _encode(delay_time),
            _encode(data_skip),
        )

    # Weather (program mode).

    def get_weather_priority(self) -> bool:
        """
        Return whether weather priority is on.
        """
        (value,) = self._query("WPR")
        return _require(_flag(value))

    def set_weather_priority(self, enabled: bool) -> None:
        """
        Switch weather priority on or off.
        """
        self._set("WPR", _encode(bool(enabled)))

    def get_same_group(self, group_number: int) -> SameGroup:
        """
        Return SAME group 1-5.
        """
        _check_same_group(group_number)
        name, *codes = self._query("SGP", str(group_number), count=9)
        return SameGroup(
            name=name,
            fips_codes=tuple(None if not code.strip("-") else code for code in codes),
        )

    def set_same_group(
        self,
        group_number: int,
        *,
        name: str | Keep = UNCHANGED,
        fips_codes: Sequence[str | None] | Keep = UNCHANGED,
    ) -> None:
        """
        Change SAME group 1-5.

        ``fips_codes`` holds up to eight six-digit codes. Positions past
        its end, and ``None`` entries, are cleared.
        """
        _check_same_group(group_number)
        if fips_codes is UNCHANGED:
            code_fields = [""] * 8
        else:
            codes = list(fips_codes)
            if len(codes) > 8:
                raise ValueError("a SAME group holds at most eight FIPS codes")
            for code in codes:
                if code is not None and not (len(code) == 6 and code.isdigit()):
                    raise ValueError(f"FIPS codes are six digits: {code!r}")
            code_fields = [code or "--------" for code in codes]
            code_fields += ["--------"] * (8 - len(code_fields))
        self._set("SGP", str(group_number), _encode_name(name), *code_fields)

    # Motorola custom band plan (program mode).

    def get_band_plan(self, system_index: int) -> tuple[BandPlanRange, ...]:
        """
        Return the six band plan ranges of a Motorola 800 custom system.
        """
        fields = self._query("MCP", str(system_index), count=24)
        return tuple(
            BandPlanRange(
                lower=_int(lower), upper=_int(upper), step=_int(step), offset=_int(offset)
            )
            for lower, upper, step, offset in zip(*[iter(fields)] * 4, strict=True)
        )

    def set_band_plan(self, system_index: int, ranges: Sequence[BandPlanRange | None]) -> None:
        """
        Set up to six band plan ranges.

        ``None`` entries and fields are left as they are. ``offset``
        runs from -1023 to 1023.
        """
        if len(ranges) > 6:
            raise ValueError("a band plan has at most six ranges")
        fields: list[str] = []
        for band in [*ranges, *[None] * (6 - len(ranges))]:
            band = band or BandPlanRange(None, None, None, None)
            fields += [
                "" if band.lower is None else _encode_frequency(band.lower),
                "" if band.upper is None else _encode_frequency(band.upper),
                _encode(band.step),
                _encode(band.offset),
            ]
        self._set("MCP", str(system_index), *fields)

    # Test mode readings.

    def get_window_voltage(self) -> tuple[int, int]:
        """
        Return the window A/D reading (0-255) and current frequency.
        """
        value, frequency = self._query("WIN", count=2)
        return _require(_int(value)), _require(_int(frequency))

    def get_battery_voltage(self) -> float:
        """
        Return the battery voltage in volts.
        """
        (value,) = self._query("BAV")
        return 3.3 * _require(_int(value)) / 255


def _raise_for_error(command: str, fields: list[str]) -> None:
    code = fields[-1] if len(fields) <= 2 else None
    if code in _ERROR_RESPONSES and (len(fields) == 1 or fields[0] == command):
        raise _ERROR_RESPONSES[code](f"{command}: {code}")


def _split_display(body: str) -> tuple[str, str, str, str, list[str]]:
    """
    Split an STS body into lines, line modes and the other fields.

    The lines are fixed-width and may contain commas, so they're
    matched by width. If the scanner didn't pad them, fall back to
    splitting on commas.
    """
    padded = _PADDED_DISPLAY.fullmatch(body)
    if padded:
        line1, modes1, line2, modes2, rest = padded.groups()
        return line1, modes1, line2, modes2, rest.split(",")
    fields = body.split(",")
    if len(fields) != 11:
        raise UnexpectedResponseError(f"can't split the STS display fields: {body!r}")
    return fields[0], fields[1], fields[2], fields[3], fields[4:]


def _display_line(text: str, modes: str) -> DisplayLine:
    modes = modes.ljust(len(text))
    return DisplayLine(text=text, modes=tuple(_enum(DisplayMode, mode) for mode in modes))


def _icons(group1: str, group2: str) -> Icons:
    if len(group1) != 15 or len(group2) != 17:
        raise UnexpectedResponseError(f"unexpected icon fields: {group1!r}, {group2!r}")
    first = [_enum(IconState, state) for state in group1]
    second = [_enum(IconState, state) for state in group2]
    return Icons(
        system=first[0],
        system_keys=dict(zip(range(1, 11), first[1:11], strict=True)),
        attenuation=first[11],
        priority=first[12],
        key_lock=first[13],
        battery=first[14],
        group=second[0],
        group_keys=dict(zip(range(1, 11), second[1:11], strict=True)),
        am=second[11],
        narrow=second[12],
        fm=second[13],
        lockout=second[14],
        function=second[15],
        close_call=second[16],
    )


def _decode_screen(value: str) -> tuple[bool, bool]:
    if len(value) != 8 or set(value) - {"0", "1"}:
        raise UnexpectedResponseError(f"unexpected pager/UHF TV screen field: {value!r}")
    return value[0] == "1", value[1] == "1"


def _check_same_group(group_number: int) -> None:
    if not 1 <= group_number <= 5:
        raise ValueError(f"SAME groups run from 1 to 5, got {group_number}")
