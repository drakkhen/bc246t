"""
Save the scanner's programming to a JSON-ready dict and write it back.

The document format is described by :data:`bc246t.schema.SCHEMA`. Both
functions expect the scanner to be in program mode already.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from .enums import Backlight, GroupType, KeyCode, Modulation, PriorityMode, SystemType
from .frequency import format_mhz
from .models import ChannelInfo, GroupInfo, SystemInfo
from .scanner import Scanner
from .schema import SCHEMA

log = logging.getLogger(__name__)

SYSTEM_DEFAULTS: dict[str, Any] = {
    "hold_time": 2,
    "lockout": False,
    "attenuation": False,
    "delay_time": 2,
    "data_skip": False,
    "emergency_alert": False,
}

GROUP_DEFAULTS: dict[str, Any] = {
    "group_type": GroupType.CHANNEL.value,
    "lockout": False,
}

CHANNEL_DEFAULTS: dict[str, Any] = {
    "search_step": 0,
    "ctcss_dcs_mode": 0,
    "ctcss_dcs_tone_lockout": False,
    "lockout": False,
    "priority": False,
    "attenuation": False,
    "alert": False,
}


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """
    How many systems, groups and channels an import wrote.
    """

    systems: int
    groups: int
    channels: int


def validate_backup(data: dict[str, Any]) -> None:
    """
    Check a backup document against the schema.

    Raises ``jsonschema.ValidationError`` describing the first problem
    found.
    """
    Draft202012Validator(SCHEMA).validate(data)


def export_programming(scanner: Scanner, *, include_defaults: bool = False) -> dict[str, Any]:
    """
    Read the settings and conventional systems into a backup.

    Settings that match the scanner's defaults are left out unless
    ``include_defaults`` is set. Trunked systems aren't supported yet
    and are skipped with a warning.
    """
    systems = []
    for system in scanner.iter_systems():
        if system.system_type is not SystemType.CONVENTIONAL:
            log.warning("skipping trunked system %r: not supported yet", system.name)
            continue
        groups = []
        for group in scanner.iter_groups(system):
            channels = [
                _prune(_channel_record(channel), CHANNEL_DEFAULTS, include_defaults)
                for channel in scanner.iter_channels(group)
            ]
            record = _prune(_group_record(group), GROUP_DEFAULTS, include_defaults)
            groups.append({**record, "channels": channels})
        record = _prune(_system_record(system), SYSTEM_DEFAULTS, include_defaults)
        systems.append({**record, "groups": groups})

    line1, line2 = scanner.get_opening_message()
    return {
        "meta": {"created_at": datetime.datetime.now().astimezone().isoformat()},
        "info": {
            "model": scanner.get_model(),
            "firmware": scanner.get_firmware_version(),
        },
        "settings": {
            "backlight": scanner.get_backlight().value,
            "battery_save": scanner.get_battery_save(),
            "key_beep": scanner.get_key_beep(),
            "greeting": [line1, line2],
            "priority_mode": int(scanner.get_priority_mode()),
        },
        "systems": systems,
    }


def import_programming(
    scanner: Scanner,
    data: dict[str, Any],
    *,
    progress: Callable[[str], None] = lambda message: None,
) -> ImportSummary:
    """
    Erase the scanner and program it from a backup document.

    Systems and groups without a ``quick_key`` get keys 1-10 in the
    order they appear. ``progress`` is called with a line of text for
    each item written.
    """
    validate_backup(data)
    settings = data["settings"]

    progress("Clearing memory")
    scanner.clear_memory()
    scanner.set_backlight(Backlight(settings["backlight"]))
    scanner.set_battery_save(settings["battery_save"])
    scanner.set_key_beep(settings["key_beep"])
    scanner.set_opening_message(*settings["greeting"])
    scanner.set_priority_mode(PriorityMode(settings["priority_mode"]))

    group_count = channel_count = 0
    for system_number, system in enumerate(data["systems"], start=1):
        progress(f"System {system['name']}")
        values = {**SYSTEM_DEFAULTS, **system}
        system_index = scanner.create_system(SystemType(system["system_type"]))
        scanner.set_system_info(
            system_index,
            name=system["name"],
            quick_key=values.get("quick_key", _default_quick_key(system_number)),
            hold_time=values["hold_time"],
            lockout=values["lockout"],
            attenuation=values["attenuation"],
            delay_time=values["delay_time"],
            data_skip=values["data_skip"],
            emergency_alert=values["emergency_alert"],
        )

        for group_number, group in enumerate(system.get("groups", []), start=1):
            progress(f"  Group {group['group_name']}")
            values = {**GROUP_DEFAULTS, **group}
            group_index = scanner.append_channel_group(system_index)
            scanner.set_group_info(
                group_index,
                name=group["group_name"],
                quick_key=values.get("quick_key", _default_quick_key(group_number)),
                lockout=values["lockout"],
            )
            group_count += 1

            for channel in group.get("channels", []):
                values = {**CHANNEL_DEFAULTS, **channel}
                progress(
                    f"    {channel['name']:<16}  {format_mhz(channel['frequency'])}"
                    f"  {channel['modulation']}"
                )
                channel_index = scanner.append_channel(group_index)
                scanner.set_channel_info(
                    channel_index,
                    name=channel["name"],
                    frequency=channel["frequency"],
                    step=values["search_step"],
                    modulation=Modulation(channel["modulation"]),
                    tone=values["ctcss_dcs_mode"],
                    tone_lockout=values["ctcss_dcs_tone_lockout"],
                    lockout=values["lockout"],
                    priority=bool(values["priority"]),
                    attenuation=values["attenuation"],
                    alert=values["alert"],
                )
                channel_count += 1

    # Leave the scanner scanning instead of on hold.
    scanner.press_key(KeyCode.SCAN)
    return ImportSummary(systems=len(data["systems"]), groups=group_count, channels=channel_count)


def _default_quick_key(position: int) -> int | None:
    return position if position <= 10 else None


def _prune(record: dict[str, Any], defaults: dict[str, Any], include_defaults: bool) -> dict:
    if include_defaults:
        return record
    return {key: value for key, value in record.items() if defaults.get(key, object()) != value}


def _system_record(system: SystemInfo) -> dict[str, Any]:
    return {
        "system_type": system.system_type.value,
        "name": system.name,
        "quick_key": system.quick_key,
        "hold_time": system.hold_time,
        "lockout": system.lockout,
        "attenuation": system.attenuation,
        "delay_time": system.delay_time,
        "data_skip": system.data_skip,
        "emergency_alert": system.emergency_alert,
    }


def _group_record(group: GroupInfo) -> dict[str, Any]:
    return {
        "group_type": group.group_type.value,
        "group_name": group.name,
        "quick_key": group.quick_key,
        "lockout": group.lockout,
    }


def _channel_record(channel: ChannelInfo) -> dict[str, Any]:
    return {
        "name": channel.name,
        "frequency": channel.frequency,
        "search_step": channel.step,
        "modulation": channel.modulation.value,
        "ctcss_dcs_mode": channel.tone,
        "ctcss_dcs_tone_lockout": channel.tone_lockout,
        "lockout": channel.lockout,
        "priority": channel.priority,
        "attenuation": channel.attenuation,
        "alert": channel.alert,
    }
