# bc246t

Control and program a Uniden Bearcat BC246T (TrunkTracker III) scanner over
its serial port. It covers every remote command in Uniden's
[BC246T PC Protocol V2.60][spec] and adds a `bc246t` command for the jobs you
do most.

## Install

Needs Python 3.11 or later.

```sh
pip install .
```

## Command line

```sh
bc246t status               # mirror the scanner's display in the terminal
bc246t info                 # model, firmware, memory and battery
bc246t export -o mine.json  # save systems, groups, channels and settings
bc246t import mine.json     # erase the scanner, then program it from a file
```

The scanner is found automatically when exactly one Prolific USB-serial
adapter (the chip in Uniden's USB-1 cable) is plugged in. Otherwise pass
`--port /dev/cu.usbserial-10` or set `BC246T_PORT`. The default speed is
57600 baud; change it with `--baudrate` to match the scanner's PC Control
setting. `--debug` logs every command and response.

Export and import handle conventional systems. Trunked systems are skipped on
export with a warning.

## Library

```python
from bc246t import Modulation, Scanner, parse_mhz

with Scanner.open() as scanner:
    print(scanner.get_status().line1.text)

    with scanner.program_mode():
        for system in scanner.iter_systems():
            for group in scanner.iter_groups(system):
                for channel in scanner.iter_channels(group):
                    print(system.name, group.name, channel.name)

        system = next(scanner.iter_systems())
        group = next(scanner.iter_groups(system))
        channel_index = scanner.append_channel(group.index)
        scanner.set_channel_info(
            channel_index,
            name="Tac 2",
            frequency=parse_mhz("154.1500"),
            modulation=Modulation.NFM,
        )
```

Most programming commands only work in program mode, which pauses scanning
and locks the keypad until you leave it. Setters take keyword arguments, and
any argument you leave out is sent as an empty field, which the scanner keeps
as it was.

Frequencies are integers in 100 Hz units, the way the scanner stores them:
`8510125` is 851.0125 MHz. `parse_mhz` and `format_mhz` convert. Tone codes
for channels are in `bc246t.tones`.

## Development

```sh
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest
```

The tests run against a simulated scanner, so no hardware is needed.

[spec]: https://info.uniden.com/twiki/pub/UnidenMan4/BC246TFirmwareUpdate/BC246T_PC_Protocol__V2.60.pdf
