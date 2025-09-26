#!/usr/bin/env python
# -*- coding: utf-8 -*-

import bc246t
import time
import signal
import sys

def main():
    format = """Free: %s%%          Batt: %.4sV
  ╔════════════════════════╗
  ║    %s    ║
  ║    %s    ║
  ║    %3.3s  %11.11s    ║
  ╚════════════════════════╝
%3.3s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s %3.3s %3.3s %5.5s %4.4s
%3.3s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s%1.1s %2.2s %1.1s%2.2s %3.3s %1.1s %1.1s"""

    i = bc246t.Interface()
    used_memory = None
    battery_voltage = None
    countdown = 0

    while True:
        if countdown == 0:
            i.enter_program_mode()
            free_memory = 100 - i.get_used_memory()
            battery_voltage = (3.3 * i.get_battery_voltage())/255
            i.exit_program_mode()

            countdown = 1000

        countdown = countdown - 1

        s = i.get_status()

        av, freq = "", ""
        if not s["squelch"]:
            av, freq = i.get_window_voltage()
            freq = "%s.%sMhz" % (freq[0:-4].lstrip("0"), freq[-4:])

        buf = format % (
            free_memory,
            battery_voltage,
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

        print(buf + "\033[%dA" % (buf.count("\n") + 1))
        time.sleep(.1)

def shutdown():
    # show cursor
    sys.stdout.write("\033[?25h\r")
    sys.stdout.flush()

def handle_sigint(sig, frame):
    shutdown()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        # hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        main()
    finally:
        shutdown()
