"""
Command-line tests, with the serial port replaced by the simulator.
"""

import json
from pathlib import Path

import pytest

from bc246t import Scanner, cli

from .simulator import SimulatedScanner, scripted
from .test_backup import BACKUP
from .test_scanner import STS


@pytest.fixture
def simulator(monkeypatch: pytest.MonkeyPatch) -> SimulatedScanner:
    simulator = SimulatedScanner()
    monkeypatch.setattr(Scanner, "open", lambda *args, **kwargs: Scanner(simulator))
    return simulator


def test_info(simulator: SimulatedScanner, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["info"]) == 0

    output = capsys.readouterr().out
    assert "Model:     BC246T" in output
    assert "Battery:   2.59 V" in output
    assert not simulator.program_mode


def test_import_then_export(
    simulator: SimulatedScanner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "in.json"
    source.write_text(json.dumps(BACKUP))
    target = tmp_path / "out.json"

    assert cli.main(["import", "--yes", str(source)]) == 0
    assert cli.main(["export", "-o", str(target)]) == 0

    assert "Wrote 2 systems, 3 groups and 4 channels." in capsys.readouterr().out
    assert json.loads(target.read_text())["systems"] == BACKUP["systems"]


def test_import_asks_before_erasing(
    simulator: SimulatedScanner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "in.json"
    source.write_text(json.dumps(BACKUP))
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    assert cli.main(["import", str(source)]) == 1
    assert "CLR" not in simulator.sent


def test_import_rejects_invalid_file(
    simulator: SimulatedScanner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "in.json"
    source.write_text(json.dumps({"systems": []}))

    assert cli.main(["import", "--yes", str(source)]) == 1
    assert "not a valid backup" in capsys.readouterr().err
    assert simulator.sent == []


def test_scanner_errors_are_reported_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scanner, _ = scripted({"PRG": "PRG,NG"})
    monkeypatch.setattr(Scanner, "open", lambda *args, **kwargs: scanner)

    assert cli.main(["info"]) == 1
    assert capsys.readouterr().err == "bc246t: PRG: NG\n"


def test_render_status() -> None:
    scanner, _ = scripted({"STS": STS})

    screen = cli.render_status(scanner.get_status(), 25, 2.6, "128", "851.0125MHz")

    assert screen.splitlines() == [
        "Memory:  75% free       Battery: 2.60 V",
        "  ╔════════════════════════╗",
        "  ║    Fire, Station 1     ║",
        "  ║     851.0125MHz        ║",
        "  ║    128  851.0125MHz    ║",
        "  ╚════════════════════════╝",
        "SYS 12 4567890 ATT               ",
        "GRP 1234567       N FM         ",
    ]
