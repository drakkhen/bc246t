"""
JSON Schema for the backup files written by ``bc246t export``.

Only conventional systems are supported. Frequencies are in 100 Hz units
and search steps in 10 Hz units, as the scanner stores them.
"""

from typing import Any

from .enums import SEARCH_STEPS, Backlight, GroupType, Modulation, PriorityMode, SystemType
from .scanner import NAME_MAX_LENGTH

_NAME = {"type": "string", "maxLength": NAME_MAX_LENGTH}
_QUICK_KEY = {"type": ["integer", "null"], "minimum": 1, "maximum": 10}

# The receive ranges of the BC246T, in 100 Hz units.
_BANDS_MHZ = ((25, 54), (108, 174), (216, 225), (400, 512), (806, 956), (1240, 1300))

CHANNEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "frequency", "modulation"],
    "additionalProperties": False,
    "properties": {
        "name": _NAME,
        "frequency": {
            "type": "integer",
            "multipleOf": 25,
            "oneOf": [
                {"minimum": low * 10_000, "maximum": high * 10_000} for low, high in _BANDS_MHZ
            ],
        },
        "search_step": {"type": "integer", "enum": list(SEARCH_STEPS)},
        "modulation": {"type": "string", "enum": [m.value for m in Modulation]},
        "ctcss_dcs_mode": {"type": "integer", "minimum": 0, "maximum": 231},
        "ctcss_dcs_tone_lockout": {"type": "boolean"},
        "lockout": {"type": "boolean"},
        # Older exports wrote priority as 0 or 1.
        "priority": {"oneOf": [{"type": "boolean"}, {"type": "integer", "enum": [0, 1]}]},
        "attenuation": {"type": "boolean"},
        "alert": {"type": "boolean"},
    },
}

GROUP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["group_name"],
    "additionalProperties": False,
    "properties": {
        "group_type": {"type": "string", "const": GroupType.CHANNEL.value},
        "group_name": _NAME,
        "quick_key": _QUICK_KEY,
        "lockout": {"type": "boolean"},
        "group_sequence": {"type": "integer", "minimum": 0},
        "channels": {"type": "array", "items": CHANNEL_SCHEMA},
    },
}

SYSTEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["system_type", "name"],
    "additionalProperties": False,
    "properties": {
        "system_type": {"type": "string", "const": SystemType.CONVENTIONAL.value},
        "name": _NAME,
        "quick_key": _QUICK_KEY,
        "hold_time": {"type": "integer", "minimum": 0, "maximum": 255},
        "lockout": {"type": "boolean"},
        "attenuation": {"type": "boolean"},
        "delay_time": {"type": "integer", "minimum": 0, "maximum": 5},
        "data_skip": {"type": "boolean"},
        "emergency_alert": {"type": "boolean"},
        "sequence_number": {"type": "integer", "minimum": 1, "maximum": 200},
        "groups": {"type": "array", "items": GROUP_SCHEMA},
    },
}

SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["info", "settings", "systems"],
    "additionalProperties": False,
    "properties": {
        "meta": {"type": "object"},
        "info": {
            "type": "object",
            "required": ["model", "firmware"],
            "properties": {
                "model": {"const": "BC246T"},
                "firmware": {"type": "string"},
            },
        },
        "settings": {
            "type": "object",
            "required": ["backlight", "battery_save", "key_beep", "greeting", "priority_mode"],
            "additionalProperties": False,
            "properties": {
                "backlight": {"type": "string", "enum": [b.value for b in Backlight]},
                "battery_save": {"type": "boolean"},
                "key_beep": {"type": "boolean"},
                "greeting": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "items": _NAME,
                },
                "priority_mode": {"type": "integer", "enum": [p.value for p in PriorityMode]},
            },
        },
        "systems": {"type": "array", "items": SYSTEM_SCHEMA},
    },
}
