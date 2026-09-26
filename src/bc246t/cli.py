"""
Command-line interface for the BC246T.

Subcommands: ``status``, ``info``, ``export`` and ``import``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from jsonschema import ValidationError

from . import __version__
from .backup import export_programming, import_programming, validate_backup
from .enums import IconState
from .errors import ScannerError
from .frequency import format_mhz
from .models import Icons, Status
from .scanner import DEFAULT_BAUDRATE, Scanner

PORT_VARIABLE = "BC246T_PORT"
STATUS_REFRESH_SECONDS = 0.1
# Reading memory and battery needs program mode, which pauses scanning.
STATUS_SLOW_REFRESH_SECONDS = 100.0

_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the command line and return the exit status.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    try:
        return args.handler(args)
    except (ScannerError, OSError) as error:
        print(f"bc246t: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bc246t", description="Control and program a Uniden BC246T scanner."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-p",
        "--port",
        default=os.environ.get(PORT_VARIABLE),
        help=f"serial port (default: ${PORT_VARIABLE}, or the one Prolific USB adapter found)",
    )
    parser.add_argument(
        "-b", "--baudrate", type=int, default=DEFAULT_BAUDRATE, help="%(default)s by default"
    )
    parser.add_argument("--debug", action="store_true", help="log every command and response")
    commands = parser.add_subparsers(title="commands", required=True)

    status = commands.add_parser("status", help="mirror the scanner's display in the terminal")
    status.set_defaults(handler=_status)

    info = commands.add_parser("info", help="show model, firmware and memory use")
    info.set_defaults(handler=_info)

    export = commands.add_parser("export", help="write the scanner's programming as JSON")
    export.add_argument("-o", "--output", type=Path, help="file to write (default: stdout)")
    export.add_argument(
        "--include-defaults", action="store_true", help="also write settings left at default"
    )
    export.set_defaults(handler=_export)

    restore = commands.add_parser("import", help="erase the scanner and program it from JSON")
    restore.add_argument("file", type=Path, help="a file written by 'bc246t export'")
    restore.add_argument("-y", "--yes", action="store_true", help="don't ask before erasing")
    restore.set_defaults(handler=_import)

    return parser


def _open(args: argparse.Namespace) -> Scanner:
    return Scanner.open(args.port, baudrate=args.baudrate)


def _info(args: argparse.Namespace) -> int:
    with _open(args) as scanner, scanner.program_mode():
        print(f"Model:     {scanner.get_model()}")
        print(f"Firmware:  {scanner.get_firmware_version()}")
        print(f"Systems:   {scanner.get_system_count()}")
        print(f"Memory:    {scanner.get_memory_used_percent()}% used, "
              f"{scanner.get_free_memory_blocks()} blocks free")  # fmt: skip
        print(f"Battery:   {scanner.get_battery_voltage():.2f} V")
    return 0


def _export(args: argparse.Namespace) -> int:
    with _open(args) as scanner, scanner.program_mode():
        data = export_programming(scanner, include_defaults=args.include_defaults)
    validate_backup(data)
    text = json.dumps(data, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def _import(args: argparse.Namespace) -> int:
    try:
        data = json.loads(args.file.read_text())
    except json.JSONDecodeError as error:
        print(f"bc246t: {args.file} is not valid JSON: {error}", file=sys.stderr)
        return 1
    try:
        validate_backup(data)
    except ValidationError as error:
        print(f"bc246t: {args.file} is not a valid backup: {error.message}", file=sys.stderr)
        return 1

    with _open(args) as scanner:
        with scanner.program_mode():
            model = scanner.get_model()
            firmware = scanner.get_firmware_version()
        if model != data["info"]["model"]:
            print(f"bc246t: this is a {model}, not a {data['info']['model']}", file=sys.stderr)
            return 1
        if firmware != data["info"]["firmware"] and not args.yes:
            print(f"The backup is from firmware {data['info']['firmware']}; "
                  f"the scanner runs {firmware}.")  # fmt: skip
            if not _confirm("Import anyway?"):
                return 1
        if not args.yes and not _confirm("This erases everything on the scanner first. Continue?"):
            return 1

        with scanner.program_mode():
            summary = import_programming(scanner, data, progress=print)

    print(f"Wrote {summary.systems} systems, {summary.groups} groups "
          f"and {summary.channels} channels.")  # fmt: skip
    return 0


def _confirm(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def _status(args: argparse.Namespace) -> int:
    if not sys.stdout.isatty():
        print("bc246t: status needs a terminal", file=sys.stderr)
        return 1

    def restore_cursor(signum: int, frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, restore_cursor)
    sys.stdout.write(_HIDE_CURSOR)
    try:
        with _open(args) as scanner:
            _run_status(scanner)
    finally:
        sys.stdout.write(_SHOW_CURSOR + "\n")
        sys.stdout.flush()
    return 0


def _run_status(scanner: Scanner) -> None:
    memory_used = battery = 0.0
    next_slow_refresh = 0.0
    while True:
        if time.monotonic() >= next_slow_refresh:
            with scanner.program_mode():
                memory_used = scanner.get_memory_used_percent()
                battery = scanner.get_battery_voltage()
            next_slow_refresh = time.monotonic() + STATUS_SLOW_REFRESH_SECONDS

        status = scanner.get_status()
        signal_level, frequency = "", ""
        if status.squelch_open:
            level, raw_frequency = scanner.get_window_voltage()
            signal_level, frequency = str(level), f"{format_mhz(raw_frequency)}MHz"

        screen = render_status(status, memory_used, battery, signal_level, frequency)
        # Draw over the last frame: print, then move the cursor up.
        sys.stdout.write(f"{screen}\033[{screen.count(chr(10))}A\r")
        sys.stdout.flush()
        time.sleep(STATUS_REFRESH_SECONDS)


def render_status(
    status: Status, memory_used: float, battery: float, signal_level: str, frequency: str
) -> str:
    """
    Draw the scanner's display as a box of text, icons underneath.
    """
    icons = status.icons
    return "\n".join(
        [
            f"Memory: {100 - memory_used:3.0f}% free       Battery: {battery:.2f} V",
            "  ╔════════════════════════╗",
            f"  ║    {status.line1.text:16.16}    ║",
            f"  ║    {status.line2.text:16.16}    ║",
            f"  ║    {signal_level:>3.3}  {frequency:>11.11}    ║",
            "  ╚════════════════════════╝",
            _icon_row("SYS", icons.system, icons.system_keys, _system_flags(icons)),
            _icon_row("GRP", icons.group, icons.group_keys, _group_flags(icons)),
            "",
        ]
    )


def _icon_row(
    label: str, icon: IconState, keys: dict[int, IconState], flags: list[tuple[str, IconState]]
) -> str:
    digits = "".join(_shown(str(key % 10), keys[key]) for key in range(1, 11))
    return " ".join([_shown(label, icon), digits, *(_shown(text, state) for text, state in flags)])


def _system_flags(icons: Icons) -> list[tuple[str, IconState]]:
    return [
        ("ATT", icons.attenuation),
        ("PRI", icons.priority),
        ("K/LCK", icons.key_lock),
        ("BATT", icons.battery),
    ]


def _group_flags(icons: Icons) -> list[tuple[str, IconState]]:
    return [
        ("AM", icons.am),
        ("N", icons.narrow),
        ("FM", icons.fm),
        ("L/O", icons.lockout),
        ("F", icons.function),
        ("CC", icons.close_call),
    ]


def _shown(text: str, state: IconState) -> str:
    return " " * len(text) if state is IconState.OFF else text


if __name__ == "__main__":
    sys.exit(main())
