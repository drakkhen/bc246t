"""
Export and import against the simulated scanner.
"""

import copy
from typing import Any

import pytest
from jsonschema import ValidationError

from bc246t import Scanner
from bc246t.backup import export_programming, import_programming, validate_backup

from .simulator import SimulatedScanner

BACKUP: dict[str, Any] = {
    "info": {"model": "BC246T", "firmware": "VR2.60"},
    "settings": {
        "backlight": "KY",
        "battery_save": True,
        "key_beep": False,
        "greeting": ["Hello", "World"],
        "priority_mode": 2,
    },
    "systems": [
        {
            "system_type": "CNV",
            "name": "Public Safety",
            "quick_key": 1,
            "hold_time": 5,
            "groups": [
                {
                    "group_name": "Fire",
                    "quick_key": 1,
                    "channels": [
                        {"name": "Dispatch", "frequency": 1540000, "modulation": "NFM"},
                        {
                            "name": "Tac 2",
                            "frequency": 1541500,
                            "modulation": "FM",
                            "ctcss_dcs_mode": 72,
                            "priority": True,
                        },
                    ],
                },
                {
                    "group_name": "EMS",
                    "quick_key": None,
                    "lockout": True,
                    "channels": [{"name": "Med 1", "frequency": 4630000, "modulation": "AUTO"}],
                },
            ],
        },
        {
            "system_type": "CNV",
            "name": "Air",
            "quick_key": 10,
            "groups": [
                {
                    "group_name": "Tower",
                    "quick_key": 1,
                    "channels": [
                        {
                            "name": "Tower",
                            "frequency": 1201000,
                            "modulation": "AM",
                            "lockout": True,
                        }
                    ],
                }
            ],
        },
    ],
}


def run_import(scanner: Scanner, data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    with scanner.program_mode():
        import_programming(scanner, data, progress=lines.append)
    return lines


def run_export(scanner: Scanner, **options: bool) -> dict[str, Any]:
    with scanner.program_mode():
        return export_programming(scanner, **options)


def test_import_then_export_round_trips(simulated: Scanner) -> None:
    run_import(simulated, BACKUP)

    exported = run_export(simulated)

    assert exported["info"] == BACKUP["info"]
    assert exported["settings"] == BACKUP["settings"]
    assert exported["systems"] == BACKUP["systems"]
    validate_backup(exported)


def test_import_reports_counts_and_progress(simulated: Scanner) -> None:
    with simulated.program_mode():
        lines: list[str] = []
        summary = import_programming(simulated, BACKUP, progress=lines.append)

    assert (summary.systems, summary.groups, summary.channels) == (2, 3, 4)
    assert "    Dispatch          154.0000  NFM" in lines


def test_import_clears_existing_programming(simulated: Scanner) -> None:
    run_import(simulated, BACKUP)
    run_import(simulated, BACKUP)

    assert len(run_export(simulated)["systems"]) == 2


def test_import_assigns_quick_keys_in_order_when_missing(
    simulated: Scanner, simulator: SimulatedScanner
) -> None:
    data = copy.deepcopy(BACKUP)
    for system in data["systems"]:
        del system["quick_key"]

    run_import(simulated, data)

    systems = [simulator.blocks[index] for index in simulator.systems]
    keys = [system.quick_key for system in systems]  # type: ignore[union-attr]
    assert keys == ["1", "2"]


def test_import_leaves_the_scanner_scanning(
    simulated: Scanner, simulator: SimulatedScanner
) -> None:
    run_import(simulated, BACKUP)

    assert "KEY,S,P" in simulator.sent


def test_export_can_include_defaults(simulated: Scanner) -> None:
    run_import(simulated, BACKUP)

    exported = run_export(simulated, include_defaults=True)

    channel = exported["systems"][0]["groups"][0]["channels"][0]
    assert channel["search_step"] == 0
    assert channel["alert"] is False
    assert exported["systems"][1]["hold_time"] == 2


def test_export_needs_program_mode(simulated: Scanner) -> None:
    from bc246t import CommandRejectedError

    with pytest.raises(CommandRejectedError):
        export_programming(simulated)


def test_old_exports_still_validate() -> None:
    data = copy.deepcopy(BACKUP)
    data["meta"] = {"created_at": "2019-01-01T00:00:00"}
    data["settings"]["backlight"] = "IF"
    data["systems"][0]["groups"][0]["channels"][0]["priority"] = 0

    validate_backup(data)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["systems"][0].update(system_type="M82S"),
        lambda d: d["systems"][0].update(name="x" * 17),
        lambda d: d["systems"][0]["groups"][0]["channels"][0].update(frequency=1000000),
        lambda d: d["systems"][0]["groups"][0]["channels"][0].update(frequency=1540001),
        lambda d: d["settings"].update(backlight="ON"),
        lambda d: d.update(extra=True),
    ],
)
def test_invalid_backups_are_rejected(change: Any) -> None:
    data = copy.deepcopy(BACKUP)
    change(data)

    with pytest.raises(ValidationError):
        validate_backup(data)


def test_export_omits_fields_the_scanner_leaves_blank(
    simulated: Scanner, simulator: SimulatedScanner
) -> None:
    run_import(simulated, BACKUP)
    first_system = simulator.blocks[simulator.systems[0]]
    first_system.emergency_alert = ""  # type: ignore[union-attr]

    exported = run_export(simulated, include_defaults=True)

    assert "emergency_alert" not in exported["systems"][0]
    validate_backup(exported)


@pytest.mark.parametrize("name", ["Fire, EMS", "Café", "Tab\there"])
def test_names_the_scanner_cant_store_fail_validation(name: str) -> None:
    data = copy.deepcopy(BACKUP)
    data["systems"][0]["groups"][0]["channels"][0]["name"] = name

    with pytest.raises(ValidationError):
        validate_backup(data)


def test_bad_names_are_caught_before_the_scanner_is_erased(
    simulated: Scanner, simulator: SimulatedScanner
) -> None:
    data = copy.deepcopy(BACKUP)
    data["settings"]["greeting"] = ["Hello, world"]

    with pytest.raises(ValidationError), simulated.program_mode():
        import_programming(simulated, data)

    assert "CLR" not in simulator.sent
