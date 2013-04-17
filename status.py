#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

import bc246t
import time
import sys

def main():
    i = bc246t.Interface()
    #i.debug = True

    format = """  ,------------------------.
  |    %s    |
  |    %s    |
  |    %3.3s  %11.11s    |
  `------------------------'
%3.3s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s %3.3s %3.3s %5.5s %4.4s
%3.3s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s %2.2s %1.1s%2.2s %3.3s %1.1s %1.1s"""

    while True:

        s = i.get_status()

        av, freq = "", ""
        if not s["squelch"]:
            av, freq = i.get_window_voltage()
            freq = "%s.%sMhz" % (freq[0:-4].lstrip("0"), freq[-4:])

        buf = format % (
            s["line1"],
            s["line2"],
            av, freq,

            s["sys_icon"]       == "0" and "   "    or "SYS",
            s["sys_1_icon"]     == "0" and " "      or "1",
            s["sys_2_icon"]     == "0" and " "      or "2",
            s["sys_3_icon"]     == "0" and " "      or "3",
            s["sys_4_icon"]     == "0" and " "      or "4",
            s["sys_5_icon"]     == "0" and " "      or "5",
            s["sys_6_icon"]     == "0" and " "      or "6",
            s["sys_7_icon"]     == "0" and " "      or "7",
            s["sys_8_icon"]     == "0" and " "      or "8",
            s["sys_9_icon"]     == "0" and " "      or "9",
            s["sys_0_icon"]     == "0" and " "      or "0",

            s["att_icon"]       == "0" and "   "    or "ATT",
            s["pri_icon"]       == "0" and "   "    or "PRI",
            s["keylock_icon"]   == "0" and "     "  or "K/LCK",
            s["batt_icon"]      == "0" and "    "   or "BATT",

            s["grp_icon"]       == "0" and "   "    or "GRP",
            s["grp_1_icon"]     == "0" and " "      or "1",
            s["grp_2_icon"]     == "0" and " "      or "2",
            s["grp_3_icon"]     == "0" and " "      or "3",
            s["grp_4_icon"]     == "0" and " "      or "4",
            s["grp_5_icon"]     == "0" and " "      or "5",
            s["grp_6_icon"]     == "0" and " "      or "6",
            s["grp_7_icon"]     == "0" and " "      or "7",
            s["grp_8_icon"]     == "0" and " "      or "8",
            s["grp_9_icon"]     == "0" and " "      or "9",
            s["grp_0_icon"]     == "0" and " "      or "0",

            s["am_icon"]        == "0" and "  "     or "AM",
            s["n_icon"]         == "0" and " "      or "N",
            s["fm_icon"]        == "0" and "  "     or "FM",
            s["lockout_icon"]   == "0" and "   "    or "L/O",
            s["f_icon"]         == "0" and " "      or "F",
            s["cc9_icon"]       == "0" and " "      or "©"
        )

        print buf + "\033[%dA" % (buf.count("\n") + 1)
        time.sleep(.1)

if __name__ == "__main__":
    main()
