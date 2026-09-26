"""
Stand-ins for the serial port: a scripted one and a simulated BC246T.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from bc246t import Scanner


class ScriptedTransport:
    """
    Answer each command with a canned response and record what was sent.

    ``responses`` maps a full command line (without the carriage return)
    to its response, or to a list of responses returned in turn.
    """

    def __init__(self, responses: dict[str, str | list[str]]) -> None:
        self.responses = {key: [value] if isinstance(value, str) else list(value)
                          for key, value in responses.items()}  # fmt: skip
        self.sent: list[str] = []
        self.timeout: float | None = 2.0
        self.timeouts_seen: list[float | None] = []
        self.closed = False
        self._pending = b""

    def write(self, data: bytes) -> int:
        line = data.decode("latin-1").removesuffix("\r")
        self.sent.append(line)
        self.timeouts_seen.append(self.timeout)
        queue = self.responses.get(line)
        if not queue:
            raise AssertionError(f"unexpected command: {line!r}")
        response = queue.pop(0) if len(queue) > 1 else queue[0]
        self._pending = f"{response}\r".encode("latin-1")
        return len(data)

    def read_until(self, expected: bytes = b"\r", size: int | None = None) -> bytes:
        pending, self._pending = self._pending, b""
        return pending

    def close(self) -> None:
        self.closed = True


def scripted(responses: dict[str, str | list[str]]) -> tuple[Scanner, ScriptedTransport]:
    """
    Return a scanner on a :class:`ScriptedTransport`, and the transport.
    """
    transport = ScriptedTransport(responses)
    return Scanner(transport), transport


@dataclass
class _Channel:
    name: str = ""
    frequency: str = "00000000"
    step: str = "0"
    modulation: str = "AUTO"
    tone: str = "0"
    tone_lockout: str = "0"
    lockout: str = "0"
    priority: str = "0"
    attenuation: str = "0"
    alert: str = "0"
    group: int = 0


@dataclass
class _Group:
    system: int
    name: str = ""
    quick_key: str = "."
    lockout: str = "0"
    channels: list[int] = field(default_factory=list)


@dataclass
class _System:
    system_type: str
    name: str = ""
    quick_key: str = "."
    hold_time: str = "2"
    lockout: str = "0"
    attenuation: str = "0"
    delay_time: str = "2"
    data_skip: str = "0"
    emergency_alert: str = "0"
    groups: list[int] = field(default_factory=list)


_FLAG = re.compile(r"[01]?$")
_NUMBER = re.compile(r"\d*$")
_QUICK_KEY = re.compile(r"[0-9.]?$")
_FREQUENCY = re.compile(r"(\d{8})?$")
_NAME = re.compile(r".{0,16}$")


class SimulatedScanner:
    """
    A BC246T with conventional systems, per the V2.60 protocol document.

    Memory is a set of numbered blocks chained in order, as on the real
    scanner. Blank fields in a set command leave the value alone, and a
    field in the wrong format makes the scanner answer ``ERR``.
    """

    def __init__(self, firmware: str = "VR2.60") -> None:
        self.firmware = firmware
        self.timeout: float | None = 2.0
        self.program_mode = False
        self.sent: list[str] = []
        self._pending = b""
        self._reset()

    def _reset(self) -> None:
        self.settings = {"BLT": "10", "BSV": "0", "KBP": "1", "PRI": "0"}
        self.opening_message = ["", ""]
        self.blocks: dict[int, _System | _Group | _Channel] = {}
        self.systems: list[int] = []
        self._next_block = 1

    # Transport interface.

    def write(self, data: bytes) -> int:
        line = data.decode("latin-1").removesuffix("\r")
        self.sent.append(line)
        command, *args = line.split(",")
        self._pending = (self._respond(command, args) + "\r").encode("latin-1")
        return len(data)

    def read_until(self, expected: bytes = b"\r", size: int | None = None) -> bytes:
        pending, self._pending = self._pending, b""
        return pending

    def close(self) -> None:
        pass

    # Command handling.

    def _respond(self, command: str, args: list[str]) -> str:
        handler: Callable[[list[str]], str] | None = getattr(self, f"_cmd_{command.lower()}", None)
        if handler is None:
            return "ERR"
        if command not in ("MDL", "VER", "PRG", "EPG", "KEY", "STS") and not self.program_mode:
            return f"{command},NG"
        try:
            return f"{command},{handler(args)}"
        except (ValueError, KeyError, IndexError, AttributeError):
            return "ERR"

    def _allocate(self, block: _System | _Group | _Channel) -> int:
        index = self._next_block
        self._next_block += 1
        self.blocks[index] = block
        return index

    @staticmethod
    def _neighbours(chain: list[int], index: int) -> tuple[str, str]:
        position = chain.index(index)
        previous = chain[position - 1] if position > 0 else -1
        following = chain[position + 1] if position + 1 < len(chain) else -1
        return str(previous), str(following)

    @staticmethod
    def _apply(
        target: object, names: list[str], values: list[str], patterns: list[re.Pattern]
    ) -> str:
        if len(values) != len(names):
            raise ValueError
        for value, pattern in zip(values, patterns, strict=True):
            if not pattern.match(value):
                raise ValueError
        for name, value in zip(names, values, strict=True):
            if value != "":
                setattr(target, name, value)
        return "OK"

    def _cmd_mdl(self, args: list[str]) -> str:
        return "BC246T"

    def _cmd_ver(self, args: list[str]) -> str:
        return self.firmware

    def _cmd_prg(self, args: list[str]) -> str:
        self.program_mode = True
        return "OK"

    def _cmd_epg(self, args: list[str]) -> str:
        self.program_mode = False
        return "OK"

    def _cmd_key(self, args: list[str]) -> str:
        return "OK"

    def _cmd_clr(self, args: list[str]) -> str:
        self._reset()
        return "OK"

    def _setting(self, command: str, args: list[str], allowed: tuple[str, ...]) -> str:
        if not args:
            return self.settings[command]
        if args[0] not in allowed:
            raise ValueError
        self.settings[command] = args[0]
        return "OK"

    def _cmd_blt(self, args: list[str]) -> str:
        return self._setting("BLT", args, ("IF", "10", "30", "KY", "SQ"))

    def _cmd_bsv(self, args: list[str]) -> str:
        return self._setting("BSV", args, ("0", "1"))

    def _cmd_kbp(self, args: list[str]) -> str:
        return self._setting("KBP", args, ("0", "1"))

    def _cmd_pri(self, args: list[str]) -> str:
        return self._setting("PRI", args, ("0", "1", "2"))

    def _cmd_oms(self, args: list[str]) -> str:
        if not args:
            return ",".join(self.opening_message)
        if len(args) != 2 or any(len(line) > 16 for line in args):
            raise ValueError
        self.opening_message = args
        return "OK"

    def _cmd_sct(self, args: list[str]) -> str:
        return str(len(self.systems))

    def _cmd_sih(self, args: list[str]) -> str:
        return str(self.systems[0]) if self.systems else "-1"

    def _cmd_sit(self, args: list[str]) -> str:
        return str(self.systems[-1]) if self.systems else "-1"

    def _cmd_mem(self, args: list[str]) -> str:
        return str(len(self.blocks) * 100 // 3000)

    def _cmd_rmb(self, args: list[str]) -> str:
        return str(3000 - len(self.blocks))

    def _cmd_bav(self, args: list[str]) -> str:
        return "200"

    def _cmd_csy(self, args: list[str]) -> str:
        (system_type,) = args
        if system_type != "CNV":
            raise ValueError
        index = self._allocate(_System(system_type))
        self.systems.append(index)
        return str(index)

    def _cmd_sin(self, args: list[str]) -> str:
        system = self.blocks[int(args[0])]
        assert isinstance(system, _System)
        if len(args) == 1:
            index = int(args[0])
            previous, following = self._neighbours(self.systems, index)
            groups = system.groups
            return ",".join([
                system.system_type, system.name, system.quick_key, system.hold_time,
                system.lockout, system.attenuation, system.delay_time, system.data_skip,
                system.emergency_alert, previous, following,
                str(groups[0]) if groups else "-1", str(groups[-1]) if groups else "-1",
                str(self.systems.index(index) + 1),
            ])  # fmt: skip
        return self._apply(
            system,
            ["name", "quick_key", "hold_time", "lockout", "attenuation", "delay_time",
             "data_skip", "emergency_alert"],
            args[1:],
            [_NAME, _QUICK_KEY, _NUMBER, _FLAG, _FLAG, _NUMBER, _FLAG, _FLAG],
        )  # fmt: skip

    def _cmd_agc(self, args: list[str]) -> str:
        system_index = int(args[0])
        system = self.blocks[system_index]
        assert isinstance(system, _System)
        index = self._allocate(_Group(system=system_index))
        system.groups.append(index)
        return str(index)

    def _cmd_gin(self, args: list[str]) -> str:
        index = int(args[0])
        group = self.blocks[index]
        assert isinstance(group, _Group)
        if len(args) == 1:
            system = self.blocks[group.system]
            assert isinstance(system, _System)
            previous, following = self._neighbours(system.groups, index)
            channels = group.channels
            return ",".join([
                "C", group.name, group.quick_key, group.lockout, previous, following,
                str(group.system), str(channels[0]) if channels else "-1",
                str(channels[-1]) if channels else "-1", str(system.groups.index(index) + 1),
            ])  # fmt: skip
        return self._apply(
            group, ["name", "quick_key", "lockout"], args[1:], [_NAME, _QUICK_KEY, _FLAG]
        )

    def _cmd_acc(self, args: list[str]) -> str:
        group_index = int(args[0])
        group = self.blocks[group_index]
        assert isinstance(group, _Group)
        index = self._allocate(_Channel(group=group_index))
        group.channels.append(index)
        return str(index)

    def _cmd_cin(self, args: list[str]) -> str:
        index = int(args[0])
        channel = self.blocks[index]
        assert isinstance(channel, _Channel)
        if len(args) == 1:
            group = self.blocks[channel.group]
            assert isinstance(group, _Group)
            previous, following = self._neighbours(group.channels, index)
            # The real scanner ends this response with a stray comma.
            return ",".join([
                channel.name, channel.frequency, channel.step, channel.modulation, channel.tone,
                channel.tone_lockout, channel.lockout, channel.priority, channel.attenuation,
                channel.alert, previous, following, str(group.system), str(channel.group), "",
            ])  # fmt: skip
        return self._apply(
            channel,
            ["name", "frequency", "step", "modulation", "tone", "tone_lockout", "lockout",
             "priority", "attenuation", "alert"],
            args[1:],
            [_NAME, _FREQUENCY, _NUMBER, re.compile(r"(AUTO|FM|NFM|AM)?$"), _NUMBER, _FLAG,
             _FLAG, _FLAG, _FLAG, _FLAG],
        )  # fmt: skip
