"""
Tests for the frequency and tone helpers.
"""

import pytest

from bc246t import format_mhz, parse_mhz
from bc246t.tones import SEARCH, ctcss_code, dcs_code, tone_label


@pytest.mark.parametrize(
    ("text", "units"), [("851.0125", 8510125), ("162.4", 1624000), (46.025, 460250)]
)
def test_parse_mhz(text: str | float, units: int) -> None:
    assert parse_mhz(text) == units


def test_parse_mhz_refuses_finer_than_100_hz() -> None:
    with pytest.raises(ValueError):
        parse_mhz("851.01255")


def test_parse_mhz_refuses_garbage() -> None:
    with pytest.raises(ValueError):
        parse_mhz("fast")


def test_format_mhz() -> None:
    assert format_mhz(8510125) == "851.0125"
    assert format_mhz(460250) == "46.0250"


def test_tone_codes_match_the_spec_table() -> None:
    assert ctcss_code(67.0) == 64
    assert ctcss_code("88.5") == 72
    assert ctcss_code(254.1) == 113
    assert dcs_code("023") == 128
    assert dcs_code(754) == 231
    assert tone_label(72) == "CTCSS 88.5 Hz"
    assert tone_label(231) == "DCS 754"
    assert tone_label(SEARCH) == "Search"


def test_unknown_tones_raise() -> None:
    with pytest.raises(ValueError):
        ctcss_code(100.1)
    with pytest.raises(ValueError):
        dcs_code("024")
    with pytest.raises(ValueError):
        tone_label(114)
