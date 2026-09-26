"""
Protocol tests: what each method sends and how it reads the reply.
"""

import pytest

from bc246t import (
    UNCHANGED,
    Alert,
    Backlight,
    BandPlanRange,
    CloseCallBand,
    CloseCallMode,
    CommandError,
    CommandRejectedError,
    DisplayMode,
    FramingError,
    IconState,
    IdMode,
    KeyCode,
    KeyMode,
    Modulation,
    NoFreeMemoryError,
    OverrunError,
    PriorityMode,
    ScannerTimeoutError,
    SystemType,
    UnexpectedResponseError,
)
from bc246t.scanner import CLEAR_MEMORY_TIMEOUT

from .simulator import scripted

LINE1 = "Fire, Station 1 "
LINE2 = " 851.0125MHz    "
STS = f"STS,{LINE1},{' ' * 16},{LINE2},{'#' * 16},112011111111000,11111111000011000,,1,0,0,0"


def test_status_slices_lines_that_contain_commas() -> None:
    scanner, _ = scripted({"STS": STS})

    status = scanner.get_status()

    assert status.line1.text == LINE1
    assert status.line2.text == LINE2
    assert set(status.line1.modes) == {DisplayMode.NORMAL}
    assert set(status.line2.modes) == {DisplayMode.BLINK}
    assert status.squelch_open
    assert not status.muted
    assert not status.weather_alert


def test_status_decodes_icons_in_lcd_order() -> None:
    scanner, _ = scripted({"STS": STS})

    icons = scanner.get_status().icons

    assert icons.system is IconState.ON
    assert icons.system_keys[1] is IconState.ON
    assert icons.system_keys[2] is IconState.BLINK
    assert icons.system_keys[3] is IconState.OFF
    assert icons.system_keys[10] is IconState.ON
    assert icons.attenuation is IconState.ON
    assert icons.battery is IconState.OFF
    assert icons.group_keys[8] is IconState.OFF
    assert icons.narrow is IconState.ON
    assert icons.close_call is IconState.OFF


def test_status_falls_back_to_commas_when_lines_are_not_padded() -> None:
    scanner, _ = scripted({"STS": "STS,Scan,,Ch 1,,000000000000000,00000000000000000,,0,0,1,$$$"})

    status = scanner.get_status()

    assert status.line1.text == "Scan"
    assert status.battery_low
    assert status.weather_alert
    assert status.same_event_code == "$$$"


def test_current_talkgroup_is_none_when_nothing_is_shown() -> None:
    scanner, _ = scripted({"GID": "GID,,,,,,"})

    assert scanner.get_current_talkgroup() is None


def test_current_talkgroup() -> None:
    scanner, _ = scripted({"GID": "GID,M82S,1234,0,County,Fire,Dispatch"})

    talkgroup = scanner.get_current_talkgroup()

    assert talkgroup is not None
    assert talkgroup.system_type is SystemType.MOTOROLA_800_TYPE2_STANDARD
    assert talkgroup.id_mode is IdMode.SCAN
    assert talkgroup.tgid_name == "Dispatch"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ("ERR", CommandError),
        ("KEY,ERR", CommandError),
        ("KEY,NG", CommandRejectedError),
        ("FER", FramingError),
        ("ORER", OverrunError),
        ("MDL,BC246T", UnexpectedResponseError),
    ],
)
def test_error_responses_raise(response: str, error: type[Exception]) -> None:
    scanner, _ = scripted({"KEY,M,P": response})

    with pytest.raises(error):
        scanner.press_key(KeyCode.MENU)


def test_incomplete_response_times_out() -> None:
    scanner, transport = scripted({"MDL": "MDL,BC2"})

    def cut_short(expected: bytes = b"\r", size: int | None = None) -> bytes:
        return b"MDL,BC2"

    transport.read_until = cut_short  # type: ignore[method-assign]

    with pytest.raises(ScannerTimeoutError):
        scanner.get_model()


def test_key_seven_sends_seven() -> None:
    scanner, transport = scripted({"KEY,7,L": "KEY,OK"})

    scanner.press_key(KeyCode.RCL, KeyMode.LONG_PRESS)

    assert transport.sent == ["KEY,7,L"]


def test_vfo_knob_only_accepts_press() -> None:
    scanner, _ = scripted({})

    with pytest.raises(ValueError):
        scanner.press_key(KeyCode.VFO_LEFT, KeyMode.HOLD)


def test_program_mode_context_exits_on_error() -> None:
    scanner, transport = scripted({"PRG": "PRG,OK", "EPG": "EPG,OK", "BLT": "BLT,IF"})

    with pytest.raises(RuntimeError), scanner.program_mode():
        assert scanner.get_backlight() is Backlight.ALWAYS_ON
        raise RuntimeError

    assert transport.sent == ["PRG", "BLT", "EPG"]


def test_clear_memory_waits_longer_and_restores_timeout() -> None:
    scanner, transport = scripted({"CLR": "CLR,OK"})

    scanner.clear_memory()

    assert transport.timeouts_seen == [CLEAR_MEMORY_TIMEOUT]
    assert transport.timeout == 2.0


def test_setters_leave_unchanged_fields_empty() -> None:
    scanner, transport = scripted({"SIN,5,Fire,,,1,,,,": "SIN,OK"})

    scanner.set_system_info(5, name="Fire", lockout=True)

    assert transport.sent == ["SIN,5,Fire,,,1,,,,"]


@pytest.mark.parametrize(("quick_key", "field"), [(None, "."), (10, "0"), (3, "3")])
def test_quick_keys_encode_ten_as_zero(quick_key: int | None, field: str) -> None:
    scanner, transport = scripted({f"GIN,9,,{field},": "GIN,OK"})

    scanner.set_group_info(9, quick_key=quick_key)

    assert transport.sent == [f"GIN,9,,{field},"]


def test_names_with_commas_are_refused() -> None:
    scanner, _ = scripted({})

    with pytest.raises(ValueError):
        scanner.set_group_info(1, name="Fire, EMS")
    with pytest.raises(ValueError):
        scanner.set_group_info(1, name="Seventeen chars!!")


def test_system_info_reads_indexes_and_quick_key() -> None:
    scanner, _ = scripted({"SIN,4": "SIN,CNV,Fire,0,2,0,1,2,0,0,-1,12,20,21,1"})

    system = scanner.get_system_info(4)

    assert system.quick_key == 10
    assert system.attenuation is True
    assert system.previous_index is None
    assert system.next_index == 12
    assert system.first_group_index == 20


def test_channel_info_tolerates_trailing_comma() -> None:
    scanner, _ = scripted({"CIN,30": "CIN,Dispatch,04600250,0,NFM,72,0,0,1,0,0,-1,31,4,20,"})

    channel = scanner.get_channel_info(30)

    assert channel.frequency == 4600250
    assert channel.modulation is Modulation.NFM
    assert channel.tone == 72
    assert channel.priority is True
    assert channel.next_index == 31


def test_channel_frequency_is_sent_as_eight_digits() -> None:
    command = "CIN,30,,00460250,,,,,,,,"
    scanner, transport = scripted({command: "CIN,OK"})

    scanner.set_channel_info(30, frequency=460250)

    assert transport.sent == [command]


def test_append_reports_full_memory() -> None:
    scanner, _ = scripted({"ACC,20": "ACC,-1"})

    with pytest.raises(NoFreeMemoryError):
        scanner.append_channel(20)


def test_append_talkgroup_group_uses_agt() -> None:
    scanner, transport = scripted({"AGT,4": "AGT,40"})

    assert scanner.append_talkgroup_group(4) == 40
    assert transport.sent == ["AGT,4"]


def test_system_quick_keys_follow_lcd_order() -> None:
    scanner, transport = scripted({"QSL": "QSL,1000000001", "QSL,0110000000": "QSL,OK"})

    assert scanner.get_system_quick_keys() == {1, 10}
    scanner.set_system_quick_keys({2, 3})
    assert transport.sent[-1] == "QSL,0110000000"


def test_group_quick_keys_query_ends_with_comma() -> None:
    scanner, transport = scripted({"QGL,7,": "QGL,0100000000"})

    assert scanner.get_group_quick_keys(7) == {2}
    assert transport.sent == ["QGL,7,"]


def test_custom_search_ranges_use_zero_for_enabled() -> None:
    scanner, transport = scripted({"CSG": "CSG,0111111110", "CSG,1011111111": "CSG,OK"})

    assert scanner.get_custom_search_ranges() == {1, 10}
    scanner.set_custom_search_ranges({2})
    assert transport.sent[-1] == "CSG,1011111111"


def test_custom_search_range_ten_is_index_zero() -> None:
    scanner, _ = scripted({"CSP,0": "CSP,Air,01080000,01370000,0,AM,0,2,0"})

    search = scanner.get_custom_search_range(10)

    assert search.lower_limit == 1080000
    assert search.modulation is Modulation.AM


def test_close_call_settings_round_trip() -> None:
    scanner, transport = scripted({"CLC": "CLC,2,1,A,10101", "CLC,1,,,01000": "CLC,OK"})

    settings = scanner.get_close_call_settings()
    scanner.set_close_call_settings(mode=CloseCallMode.PRIORITY, bands=[CloseCallBand.AIR])

    assert settings.mode is CloseCallMode.DO_NOT_DISTURB
    assert settings.alert is Alert.BEEP_AND_LIGHT
    assert settings.bands == {
        CloseCallBand.VHF_LOW,
        CloseCallBand.VHF_HIGH,
        CloseCallBand.BAND_800_PLUS,
    }
    assert transport.sent[-1] == "CLC,1,,,01000"


def test_search_settings_decode_screens() -> None:
    scanner, _ = scripted({"SCO": "SCO,0,AUTO,0,2,1,0,01000000,1,256"})

    settings = scanner.get_search_settings()

    assert settings.pager_screen is False
    assert settings.uhf_tv_screen is True
    assert settings.repeater_find is True
    assert settings.max_auto_store == 256


def test_tune_encodes_both_screens_without_reading_back() -> None:
    scanner, transport = scripted({"QSH,01621000,,NFM,,,,,10000000,": "QSH,OK"})

    scanner.tune(1621000, modulation=Modulation.NFM, pager_screen=True, uhf_tv_screen=False)

    assert transport.sent == ["QSH,01621000,,NFM,,,,,10000000,"]


def test_global_lockouts_iterate_until_minus_one() -> None:
    scanner, _ = scripted({"GLF": ["GLF,01621000", "GLF,04600250", "GLF,-1"]})

    assert list(scanner.iter_global_lockouts()) == [1621000, 4600250]


def test_same_group_clears_missing_codes() -> None:
    command = "SGP,2,Coast,006037," + ",".join(["--------"] * 7)
    scanner, transport = scripted({command: "SGP,OK"})

    scanner.set_same_group(2, name="Coast", fips_codes=["006037"])

    assert transport.sent == [command]


def test_same_group_reads_dashes_as_none() -> None:
    codes = ",".join(["006037", *["--------"] * 7])
    scanner, _ = scripted({"SGP,1": f"SGP,Coast,{codes}"})

    group = scanner.get_same_group(1)

    assert group.fips_codes[0] == "006037"
    assert group.fips_codes[1:] == (None,) * 7


def test_band_plan_has_six_ranges() -> None:
    fields = ",".join(["08510000,08600000,1250,0"] + [",,,"] * 5)
    scanner, transport = scripted({"MCP,3": f"MCP,{fields}", f"MCP,3,{fields}": "MCP,OK"})

    plan = scanner.get_band_plan(3)
    scanner.set_band_plan(3, [BandPlanRange(8510000, 8600000, 1250, 0)])

    assert len(plan) == 6
    assert plan[0] == BandPlanRange(8510000, 8600000, 1250, 0)
    assert plan[1] == BandPlanRange(None, None, None, None)
    assert transport.sent[-1] == f"MCP,3,{fields}"


def test_trunk_info() -> None:
    fields = "0,1,1,,0,0,16,1234ABCD,,,,,,,,,,50,51,-1,-1"
    scanner, _ = scripted({"TRN,8": f"TRN,{fields}"})

    trunk = scanner.get_trunk_info(8)

    assert trunk.id_search is False
    assert trunk.edacs_afs_format is None
    assert trunk.fleet_map == 16
    assert trunk.custom_fleet_map == "1234ABCD"
    assert trunk.bands[0].base is None
    assert trunk.first_talkgroup_group_index == 50
    assert trunk.first_lockout_group_index is None


def test_trunk_frequency_sends_channel_index() -> None:
    scanner, transport = scripted({"TFQ,61": "TFQ,08510125,,-1,62,8,60"})

    frequency = scanner.get_trunk_frequency(61)

    assert frequency.frequency == 8510125
    assert frequency.lcn is None
    assert transport.sent == ["TFQ,61"]


def test_set_talkgroup_includes_index() -> None:
    scanner, transport = scripted({"TIN,70,Dispatch,1234,,1": "TIN,OK"})

    scanner.set_talkgroup_info(70, name="Dispatch", tgid="1234", alert=True)

    assert transport.sent == ["TIN,70,Dispatch,1234,,1"]


def test_priority_mode_round_trip() -> None:
    scanner, transport = scripted({"PRI": "PRI,2", "PRI,1": "PRI,OK"})

    assert scanner.get_priority_mode() is PriorityMode.PLUS
    scanner.set_priority_mode(PriorityMode.ON)
    assert transport.sent[-1] == "PRI,1"


def test_battery_voltage_is_in_volts() -> None:
    scanner, _ = scripted({"BAV": "BAV,255"})

    assert scanner.get_battery_voltage() == pytest.approx(3.3)


def test_unchanged_repr() -> None:
    assert repr(UNCHANGED) == "UNCHANGED"


def test_context_manager_closes_the_port() -> None:
    scanner, transport = scripted({})

    with scanner:
        pass

    assert transport.closed


def test_tune_needs_both_screens_or_neither() -> None:
    scanner, transport = scripted({})

    with pytest.raises(ValueError, match="both"):
        scanner.tune(1621000, pager_screen=True)

    assert transport.sent == []


def test_set_search_settings_reads_back_the_other_screen() -> None:
    scanner, transport = scripted(
        {
            "SCO": "SCO,0,AUTO,0,2,1,0,01000000,1,256",
            "SCO,,,,,,,11000000,,": "SCO,OK",
        }
    )

    scanner.set_search_settings(pager_screen=True)

    assert transport.sent == ["SCO", "SCO,,,,,,,11000000,,"]


def test_copy_system_reports_full_memory() -> None:
    scanner, _ = scripted({"CPS,4,Copy": "CPS,-1"})

    with pytest.raises(NoFreeMemoryError):
        scanner.copy_system(4, "Copy")


def test_names_outside_printable_ascii_are_refused() -> None:
    scanner, _ = scripted({})

    with pytest.raises(ValueError):
        scanner.set_group_info(1, name="Café")
