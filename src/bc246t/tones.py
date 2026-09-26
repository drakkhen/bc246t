"""
CTCSS and DCS codes, from Uniden's BC246T protocol document.

Channels store their subaudible tone as a code from 0 to 231: 0 for
none, 127 for tone search, 64-113 for the CTCSS tones and 128-231
for the DCS codes.
"""

NONE = 0
SEARCH = 127

_CTCSS_HZ = """
67.0 69.3 71.9 74.4 77.0 79.7 82.5 85.4 88.5 91.5 94.8 97.4 100.0 103.5 107.2
110.9 114.8 118.8 123.0 127.3 131.8 136.5 141.3 146.2 151.4 156.7 159.8 162.2
165.5 167.9 171.3 173.8 177.3 179.9 183.5 186.2 189.9 192.8 196.6 199.5 203.5
206.5 210.7 218.1 225.7 229.1 233.6 241.8 250.3 254.1
""".split()

_DCS = """
023 025 026 031 032 036 043 047 051 053 054 065 071 072 073 074 114 115 116
122 125 131 132 134 143 145 152 155 156 162 165 172 174 205 212 223 225 226
243 244 245 246 251 252 255 261 263 265 266 271 274 306 311 315 325 331 332
343 346 351 356 364 365 371 411 412 413 423 431 432 445 446 452 454 455 462
464 465 466 503 506 516 523 526 532 546 565 606 612 624 627 631 632 654 662
664 703 712 723 731 732 734 743 754
""".split()

_LABELS: dict[int, str] = {
    NONE: "None",
    SEARCH: "Search",
    **{64 + i: f"CTCSS {hz} Hz" for i, hz in enumerate(_CTCSS_HZ)},
    **{128 + i: f"DCS {code}" for i, code in enumerate(_DCS)},
}

_CODES_BY_KEY: dict[str, int] = {
    **{hz: 64 + i for i, hz in enumerate(_CTCSS_HZ)},
    **{f"D{code}": 128 + i for i, code in enumerate(_DCS)},
}


def tone_label(code: int) -> str:
    """
    Describe a tone code, e.g. ``72`` -> ``"CTCSS 88.5 Hz"``.
    """
    try:
        return _LABELS[code]
    except KeyError:
        raise ValueError(f"unknown CTCSS/DCS code: {code}") from None


def ctcss_code(hz: float | str) -> int:
    """
    Return the code for a CTCSS tone, e.g. ``88.5`` -> ``72``.
    """
    key = f"{float(hz):.1f}"
    if key not in _CODES_BY_KEY:
        raise ValueError(f"not a CTCSS tone the BC246T supports: {hz}")
    return _CODES_BY_KEY[key]


def dcs_code(code: int | str) -> int:
    """
    Return the code for a DCS code, e.g. ``"023"`` or ``23`` -> ``128``.
    """
    key = f"D{int(str(code), 10):03d}"
    if key not in _CODES_BY_KEY:
        raise ValueError(f"not a DCS code the BC246T supports: {code}")
    return _CODES_BY_KEY[key]
