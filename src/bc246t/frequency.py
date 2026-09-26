"""
Conversions for the scanner's frequency format.

The scanner writes frequencies as whole numbers of 100 Hz: ``8510125``
is 851.0125 MHz. The rest of this package uses that integer form
unchanged.
"""

from decimal import Decimal, InvalidOperation

_UNITS_PER_MHZ = 10_000


def parse_mhz(value: str | float | Decimal) -> int:
    """
    Convert MHz, such as ``"851.0125"``, to scanner units.

    Raises ``ValueError`` if the value isn't a number or is finer
    than 100 Hz.
    """
    try:
        units = Decimal(str(value)) * _UNITS_PER_MHZ
    except InvalidOperation:
        raise ValueError(f"not a frequency: {value!r}") from None
    if units != units.to_integral_value():
        raise ValueError(f"{value} MHz is not a multiple of 100 Hz")
    return int(units)


def format_mhz(frequency: int) -> str:
    """
    Format scanner units as MHz: ``8510125`` -> ``"851.0125"``.
    """
    return f"{Decimal(frequency) / _UNITS_PER_MHZ:.4f}"
