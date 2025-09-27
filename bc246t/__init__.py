#!/usr/bin/env python

import os
import serial
from .constants import *
from .errors import *
from .schema import schema

SYSTEM_DEFAULTS = {
    'quick_key': None,
    'hold_time': 2,
    'lockout': False,
    'attenuation': False,
    'delay_time': 2,
    'data_skip': False,
    'emergency_alert': False,
}

GROUP_DEFAULTS = {
    'group_type': 'C',
    'lockout': False,
}

CHANNEL_DEFAULTS = {
    'search_step': 0,
    'ctcss_dcs_mode': 0,
    'ctcss_dcs_tone_lockout': False,
    'lockout': False,
    'priority': 0,
    'attenuation': False,
    'alert': False,
}

def _decode_icon(v):
    if v == "0": return ICON_OFF
    if v == "1": return ICON_ON
    if v == "2": return ICON_BLINK

    raise UnidenUnexpectedResponseError


class Interface:
    def __init__(self, port="/dev/ttyS0", baudrate=57600):
        self.device = serial.Serial(port=port, baudrate=baudrate)
        self.debug = 'DEBUG' in os.environ

    def __send(self, buf):
        self.device.write(("%s\r" % buf).encode())

        if self.debug:
            print("SEND -> %s" % buf)

        buf = ""

        while len(buf) == 0 or buf[-1] != "\r":
            recv = self.device.read(1).decode()

            if len(recv) == 0:
                raise Exception("timeout!")

            buf += recv

        buf = buf.rstrip("\r")
        res = buf.split(",")

        if len(res) == 1 and res[0] == "ERR" or len(res) == 2 and res[1] == "ERR":
            raise UnidenValueError

        if len(res) == 1 and res[0] == "NG" or len(res) == 2 and res[1] == "NG":
            raise UnidenSyncError

        if self.debug:
            print("RECV -> %s" % repr(res))

        return res

    def _send(self, cmd, *args):
        prepared = [cmd]

        for v in args:
            if v.__class__ is bool:
                v = v and 1 or 0
            prepared.append(str(v))

        return self.__send(','.join(prepared))

    ########################################################################
    ##  Remote Control
    ########################################################################

    def get_current_talkgroup_id_status(self):
        """
        Get Current Talkgroup ID Status.

        This command returns TGID currently displayed on LCD.  Returned dict has
        the following keys:

            system_type
            tgid
            id_search_mode
            system_name
            group_name
            tgid_name

        id_search_mode value will be one of

        FIXME

        When TGID is not displayed, all values will be ""
        """
        cmd, sys_type, tgid, id_srch_mode, name1, name2, name3 = self._send("GID")

        if cmd != "GID" or (id_srch_mode != "" and id_srch_mode not in MODE__VALUES):
            raise UnidenUnexpectedResponseError

        return {
            "system_type": sys_type,
            "tgid": tgid,
            "id_search_mode": id_srch_mode,
            "system_name": name1,
            "group_name": name2,
            "tgid_name": name3
        }

    def push_key(self, key, mode=KEY_MODE_PRESS):
        """
        Send a key-press to the unit.

        The key must be one of the following values:

            KEY_CODE_MENU
            KEY_CODE_F
            KEY_CODE_H
            KEY_CODE_SCAN
            KEY_CODE_L
            KEY_CODE_LIGHT
            KEY_CODE_1
            KEY_CODE_2
            KEY_CODE_3
            KEY_CODE_4
            KEY_CODE_5
            KEY_CODE_6
            KEY_CODE_7
            KEY_CODE_8
            KEY_CODE_9
            KEY_CODE_0
            KEY_CODE_DOT
            KEY_CODE_E
            KEY_CODE_VFO_RIGHT
            KEY_CODE_VFO_LEFT
            KEY_CODE_VFO_PUSH
            KEY_CODE_POWER

        The mode must be one fo the follwoing values:

            KEY_MODE_PRESS
            KEY_MODE_LONG
            KEY_MODE_HOLD
            KEY_MODE_RELEASE

        The scanner cannot be turned off by this command--I have no idea why
        there is a KEY_CODE_POWER value.  If you want to power the scanner off,
        see power_off().
        """
        if key not in KEY_CODE__VALUES or mode not in KEY_MODE__VALUES:
            raise ValueError

        cmd, ok = self._send("KEY", key, mode)

        if cmd != "KEY":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def power_off(self):
        """
        Turns off the scanner.

        Note that once it's turned off, you cannot turn it back on or otherwise
        control the scanner via the serial port.
        """
        cmd, ok = self._send("POF")

        if cmd != "POF":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def quick_search_hold(self):
        # TODO
        pass

    def get_status(self):
        """
        Returns the scanner's current status.

        The returned dict has the following keys:

            Strings representing the text on the screen.

                line1
                line2

            Display modes for the above strings.
 
                line1_mode
                line2_mode

                    The associated values will be one of:

                        DISPLAY_LINE_MODE_NORMAL
                        DISPLAY_LINE_MODE_REVERSE
                        DISPLAY_LINE_MODE_CURSOR
                        DISPLAY_LINE_MODE_BLINK

            States of icons on the display.

                sys_icon
                sys_1_icon
                sys_2_icon
                sys_3_icon
                sys_4_icon
                sys_5_icon
                sys_6_icon
                sys_7_icon
                sys_8_icon
                sys_9_icon
                sys_9_icon
                sys_0_icon

                att_icon
                pri_icon
                keylock_icon
                batt_icon

                grp_icon
                grp_1_icon
                grp_2_icon
                grp_3_icon
                grp_4_icon
                grp_5_icon
                grp_6_icon
                grp_7_icon
                grp_8_icon
                grp_9_icon
                grp_0_icon

                am_icon
                n_icon
                fm_icon
                lockout_icon
                f_icon
                cc9_icon

                    The associated values will be one of:

                        ICON_OFF
                        ICON_ON
                        ICON_BLINK

            Other misc attrubutes.  The associated values are boolean.

                squelch
                mute
                low_battery
                weather_alert
        """
        cmd, l1_char, l1_mode, l2_char, l2_mode, icon1, icon2, reserve, sql, \
            mut, bat, wat = self._send("STS")

        #l1_char = l1_char.rstrip()
        l1_mode = l1_mode.strip()
        #l2_char = l2_char.rstrip()
        l2_mode = l2_mode.strip()

        if len(l1_mode) == 0:
            l1_mode = " "

        if len(l2_mode) == 0:
            l2_mode = " "

        if cmd != "STS":
            raise UnidenUnexpectedResponseError

        if l1_mode not in DISPLAY_LINE_MODE__VALUES or l2_mode not in DISPLAY_LINE_MODE__VALUES:
            raise UnidenUnexpectedResponseError

        return {
            "line1": l1_char,
            "line1_mode": l1_mode,
            "line2": l2_char,
            "line2_mode": l2_mode,

            "sys_icon": _decode_icon(icon1[0]),
            "sys_1_icon": _decode_icon(icon1[1]),
            "sys_2_icon": _decode_icon(icon1[2]),
            "sys_3_icon": _decode_icon(icon1[3]),
            "sys_4_icon": _decode_icon(icon1[4]),
            "sys_5_icon": _decode_icon(icon1[5]),
            "sys_6_icon": _decode_icon(icon1[6]),
            "sys_7_icon": _decode_icon(icon1[7]),
            "sys_8_icon": _decode_icon(icon1[8]),
            "sys_9_icon": _decode_icon(icon1[9]),
            "sys_9_icon": _decode_icon(icon1[9]),
            "sys_0_icon": _decode_icon(icon1[10]),

            "att_icon": _decode_icon(icon1[11]),
            "pri_icon": _decode_icon(icon1[12]),
            "keylock_icon": _decode_icon(icon1[13]),
            "batt_icon": _decode_icon(icon1[14]),

            "grp_icon": _decode_icon(icon2[0]),
            "grp_1_icon": _decode_icon(icon2[1]),
            "grp_2_icon": _decode_icon(icon2[2]),
            "grp_3_icon": _decode_icon(icon2[3]),
            "grp_4_icon": _decode_icon(icon2[4]),
            "grp_5_icon": _decode_icon(icon2[5]),
            "grp_6_icon": _decode_icon(icon2[6]),
            "grp_7_icon": _decode_icon(icon2[7]),
            "grp_8_icon": _decode_icon(icon2[8]),
            "grp_9_icon": _decode_icon(icon2[9]),
            "grp_0_icon": _decode_icon(icon2[10]),

            "am_icon": _decode_icon(icon2[11]),
            "n_icon": _decode_icon(icon2[12]),
            "fm_icon": _decode_icon(icon2[13]),
            "lockout_icon": _decode_icon(icon2[14]),
            "f_icon": _decode_icon(icon2[15]),
            "cc9_icon": _decode_icon(icon2[16]),

            "squelch": sql == "0",
            "mute": mut == "1",
            "low_battery": bat == "1",
            "weather_alert": wat == "1"
        }

    ########################################################################
    ##  System Information
    ########################################################################

    def get_model(self):
        """Returns model information"""
        cmd, model = self._send("MDL")

        if cmd != "MDL":
            raise UnidenUnexpectedResponseError

        return model

    def get_firmware_version(self):
        """Returns firmware version"""
        cmd, ver = self._send("VER")

        if cmd != "VER":
            raise UnidenUnexpectedResponseError

        return ver

    ########################################################################
    ##  Programming Mode Control
    ########################################################################

    def enter_program_mode(self):
        """
        Enter program mode.

        The Scanner displays "Remote Mode" on upper line and "Keypad Lock" on
        lower line in Program Mode.  And POWER key and Function key are valid
        in Program Mode.

        This command is invalid when the Scanner is in Menu Mode, during Direct
        Entry operation, and during Quick Save operation. 
        """
        cmd, ok = self._send("PRG")

        if cmd != "PRG":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def exit_program_mode(self):
        """Exit Program Mode, and goes back in to Scan Hold Mode."""
        cmd, ok = self._send("EPG")

        if cmd != "EPG":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    ########################################################################
    ##  System Settings
    ########################################################################

    def get_backlight(self):
        """
        Get the current backlight setting.

        Returns one of:

            FIXME
        """
        cmd, val = self._send("BLT")

        if cmd != "BLT" or val not in BACKLIGHT__VALUES:
            raise UnidenUnexpectedResponseError

        return val

    def set_backlight(self, setting):
        """
        Set the backlight mode.

        Setting must be one of:

            FIXME

        This command is only acceptable in Programming Mode.
        """
        if setting not in BACKLIGHT__VALUES:
            raise ValueError

        cmd, ok = self._send("BLT", setting)

        if cmd != "BLT":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_battery_savings_mode(self):
        """
        Get the current battery savings mode setting.

        Returned value will be one of:

            BATT_SAVE_ON
            BATT_SAVE_OFF
        """
        cmd, val = self._send("BSV")

        if cmd != "BSV" or val not in BATT_SAVE__VALUES:
            raise UnidenUnexpectedResponseError

        return val == "1"

    def set_battery_savings_mode(self, setting):
        """
        Set the battery savings mode.

        Setting must be one of:

            BATT_SAVE_ON
            BATT_SAVE_OFF

        This command is only acceptable in Programming Mode.
        """
        if setting not in [True, False]:
            raise ValueError

        cmd, ok = self._send("BSV", setting)

        if cmd != "BSV":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def clear_all_memory(self):
        """
        All the memories are set for initial setting (except for serial baud rate
        value, which is retained).

        This command is only acceptable in Programming Mode.
        """
        cmd, ok = self._send("CLR")

        if cmd != "CLR":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_key_beep(self):
        """
        Get the key beep setting.

        This command is only acceptable in Programming Mode.
        """
        cmd, val = self._send("KBP")

        if cmd != "KBP" or val not in ("0", "1"):
            raise UnidenUnexpectedResponseError

        return val == "1"

    def set_key_beep(self, setting):
        """
        Get the key beep setting.

        This command is only acceptable in Programming Mode.
        """
        if setting not in (True, False):
            raise ValueError

        cmd, ok = self._send("KBP", setting)

        return ok == "OK"

    def get_greeting(self):
        """
        Get the two lines of text being used as the greeting.

        If the default message is being used, the returned values will be
        GREETING_DEFAULT ('%s').
        """ % GREETING_DEFAULT
        cmd, line1, line2 = self._send("OMS")

        if cmd != "OMS":
            raise UnidenUnexpectedResponseError

        return [line1, line2]

    def set_greeting(self, line1, line2=""):
        """
        Set the two line greeting.

        Each line can only be %d characters, max.  If you supply a larger string
        it will be truncated.

        To restore the default greeting, supply the GREETING_DEFAULT ('%s') value
        for each line.

        If the second line is not given it will be blank.
        """ % (GREETING_MAX_LINE_LEN, GREETING_DEFAULT)
        line1 = line1[:GREETING_MAX_LINE_LEN]
        line2 = line2[:GREETING_MAX_LINE_LEN]

        cmd, ok = self._send("OMS", line1, line2)

        if cmd != "OMS":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_priority_mode(self):
        """
        Get the Priority Mode.

        The returned value will be one of:

            PRIORITY_MODE_OFF
            PRIORITY_MODE_ON
            PRIORITY_MODE_PLUS

        This command is only acceptable in Programming Mode.
        """
        cmd, val = self._send("PRI")

        if cmd != "PRI" or val not in PRIORITY_MODE__VALUES:
            raise UnidenUnexpectedResponseError

        return int(val)

    def set_priority_mode(self, setting):
        """
        Set the Priority Mode.

        The given setting must be one of:

            PRIORITY_MODE_OFF
            PRIORITY_MODE_ON
            PRIORITY_MODE_PLUS

        This command is only acceptable in Programming Mode.
        """
        if setting not in [True, False]:
            raise ValueError

        cmd, ok = self._send("PRI", setting)

        if cmd != "PRI":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    ########################################################################
    ##  Scan Settings
    ########################################################################

    def get_system_count(self):
        """
        Returns the number (0-200) of stored Systems.

        This command is only acceptable in Programming Mode.
        """
        cmd, val = self._send("SCT")

        if cmd != "SCT":
            raise UnidenUnexpectedResponseError

        return val

    def get_system_index_head(self):
        """
        Returns the first index of stored system list.

        This command is only acceptable in Programming Mode.
        """
        cmd, val = self._send("SIH")

        if cmd != "SIH":
            raise UnidenUnexpectedResponseError

        return int(val)

    def get_system_index_tail(self):
        """
        Returns the last index of stored system list.

        This command is only acceptable in Programming Mode.
        """
        cmd, val = self._send("SIT")

        if cmd != "SIT":
            raise UnidenUnexpectedResponseError

        return int(val)

    def __quick_lockout_common(self, command, setting=None):
        """
        Common code for the lockout commands.  Not indended for direct use.
        """
        # Order is significant
        valid_values = QUICK_LOCKOUT_KEY__VALUES[:].sort()

        idx = 0

        if setting == None:
            # Get
            result = 0

            cmd, val = self._send(command)

            if cmd != command or len(val) != len(valid_values):
                raise UnidenUnexpectedResponseError

            for v in range(len(valid_values)):
                if val[v] == "1":
                    res += valid_values[v]

            return v

        # Set
        setting = int(setting)
        val = ""

        for v in range(len(valid_values)):
            val += setting & valid_values[v] != 0 and "1" or "0"

        cmd, ok = self._send(command, val)

        if cmd != command:
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_system_quick_lockout(self):
        """
        Get System Quick Lockout statuses.

        Returns an integer that is the sum of bits representing locked-out
        systems.  This integer should be ANDed with the following values to
        determind lockout status:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9

        For example:

            res = x.get_system_quick_lockout()

            if res & QUICK_LOCKOUT_KEY_5 != 0:
                print "System 5 is locked out"
        """
        return self.__quick_lockout_common("QSL")

    def set_system_quick_lockout(self, setting):
        """
        Set System Quick Lockout statuses.

        Given setting must be an integer that is the sum of all desired
        lockedout systems, each represented by one of the of:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9

        For example:

            old_setting = x.get_system_quick_lockout()
            new_setting = old_setting + QUICK_LOCKOUT_KEY_5

            x.set_system_quick_lockout(new_setting)

            print "System 5 is now locked out"
        """
        return self.__quick_lockout_common("QSL", setting)

    def quick_lock_system(self, k):
        """
        Lockout a given system.

        The value must be one of:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9
        """
        if k not in QUICK_LOCKOUT_KEY__VALUES:
            raise ValueError

        new_setting = cur_setting = get_system_quick_lockout()

        if cur_setting & k == 0:
            new_setting += k
            self.set_system_quick_lockout(new_setting)

        return new_setting

    def quick_unlock_system(self, k):
        """
        Un-Lockout a given system.

        The value must be one of:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9
        """
        if k not in QUICK_LOCKOUT_KEY__VALUES:
            raise ValueError

        new_setting = cur_setting = get_system_quick_lockout()

        if cur_setting & k != 0:
            new_setting -= k
            self.set_ssytem_quick_lockout(new_setting)

        return new_setting

    def get_group_quick_lockout(self):
        """
        Get Group Quick Lockout statuses.

        Returns an integer that is the sum of bits representing locked-out
        groups.  This integer should be ANDed with the following values to
        determind lockout status:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9

        For example:

            res = x.get_group_quick_lockout()

            if res & QUICK_LOCKOUT_KEY_5 != 0:
                print "Group 5 is locked out"
        """
        return self.__quick_lockout_common("QGL")

    def set_group_quick_lockout(self, setting):
        """
        Set Group Quick Lockout statuses.

        Given setting must be an integer that is the sum of all desired
        lockedout gruop, each represented by one of the of:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9

        For example:

            old_setting = x.get_group_quick_lockout()
            new_setting = old_setting + QUICK_LOCKOUT_KEY_5

            x.set_group_quick_lockout(new_setting)

            print "Group 5 is now locked out"
        """
        return self.__quick_lockout_common("QGL", setting)

    def quick_lock_group(self, k):
        """
        Lockout a given group.

        The value must be one of:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9
        """
        if k not in QUICK_LOCKOUT_KEY__VALUES:
            raise ValueError

        new_setting = cur_setting = get_group_quick_lockout()

        if cur_setting & k == 0:
            new_setting += k
            self.set_group_quick_lockout(new_setting)

        return new_setting

    def quick_unlock_group(self, k):
        """
        Un-Lockout a given group.

        The value must be one of:

            QUICK_LOCKOUT_KEY_0
            QUICK_LOCKOUT_KEY_1
            QUICK_LOCKOUT_KEY_2
            QUICK_LOCKOUT_KEY_3
            QUICK_LOCKOUT_KEY_4
            QUICK_LOCKOUT_KEY_5
            QUICK_LOCKOUT_KEY_6
            QUICK_LOCKOUT_KEY_7
            QUICK_LOCKOUT_KEY_8
            QUICK_LOCKOUT_KEY_9
        """
        if k not in QUICK_LOCKOUT_KEY__VALUES:
            raise ValueError

        new_setting = cur_setting = get_group_quick_lockout()

        if cur_setting & k != 0:
            new_setting -= k
            self.set_ssytem_quick_lockout(new_setting)

        return new_setting

    def create_system(self, system_type):
        """
        Creates a system and returns the new system's index.

        system_type must be one of:

            SYSTEM_TYPE_CONVENTIONAL
            SYSTEM_TYPE_MOT_800_T2_STD
            SYSTEM_TYPE_MOT_800_T2_SPL
            SYSTEM_TYPE_MOT_900_T2
            SYSTEM_TYPE_MOT_VHF_T2
            SYSTEM_TYPE_MOT_UHF_T2
            SYSTEM_TYPE_MOT_800_T1_STD
            SYSTEM_TYPE_MOT_800_T1_SPL
            SYSTEM_TYPE_EDACS_NARROW
            SYSTEM_TYPE_EDACS_WIDE
            SYSTEM_TYPE_EDACS_SCAT
            SYSTEM_TYPE_LTR
            SYSTEM_TYPE_MOT_800_T2_CUS
            SYSTEM_TYPE_MOT_800_T1_CUS

        This command is only acceptable in Programming Mode.
        """
        if not system_type in SYSTEM_TYPE__VALUES:
            raise ValueError

        cmd, idx = self._send("CSY", system_type)

        if cmd != "CSY":
            raise UnidenUnexpectedResultError

        if idx == "-1":
            raise UnidenOutOfResourcesError

        return int(idx)

    def delete_system(self, idx):
        """
        Delete a system found at the given index.

        This command is only acceptable in Programming Mode.
        """
        cmd, ok = self._send("DSY", idx)

        if cmd != "DSY":
            raise UnidenUnexpectedResultError

        return ok == "OK"

    def copy_system(self, idx, name):
        """
        Copies an Existing System.

        idx is the index of the system that is to be copied; name is the name
        of the new system.

        The index of the newly created system will be returned to the caller.

        This command is only acceptable in Programming Mode.
        """
        cmd, new_idx = self.__self("CPS", idx, name)

        if cmd != "CPS":
            raise UnidenUnexpectedResultError

        return new_idx

    def get_system_info(self, idx):
        """
        Returns a bunch of information on the System found at the given index.

        The returned dict has the following keys:

            index
            system_type
            name
            quick_key
            hold_time
            lockout
            attenuation
            delay_time
            data_skip
            emergency_alert
            reverse_index
            forward_index
            group_head_index
            group_tail_index
            sequnce_number

        This command is only acceptable in Programming Mode.
        """
        cmd, sys_type, name, quick_key, hld, lout, att, dly, skp, emg, rev_index, \
            fwd_index, chn_grp_head, chn_grp_tail, seq_no = self._send("SIN", idx)

        if cmd != "SIN":
            raise UnidenUnexpectedResultError

        return {
            "system_type": sys_type,
            "name": name,
            "quick_key": quick_key != '.' and int(quick_key) or None,
            "hold_time": int(hld),
            "lockout": lout == "1",
            "attenuation": att == "1",
            "delay_time": int(dly),
            "data_skip": skp == "1",
            "emergency_alert": emg == "1",
            "reverse_index": rev_index != "-1" and int(rev_index) or None,
            "forward_index": fwd_index != "-1" and int(fwd_index) or None,
            "group_head_index": int(chn_grp_head),
            "group_tail_index": int(chn_grp_tail),
            "sequence_number": int(seq_no)
        }

    def set_system_info(self, index, name, v={}):
        for k in SYSTEM_DEFAULTS.keys():
            if v.get(k) is None:
                v[k] = SYSTEM_DEFAULTS[k]

        if v['quick_key'] is None:
            v['quick_key'] = '.'

        cmd, ok = self._send("SIN", index, name, v['quick_key'], v['hold_time'],
            v['lockout'], v['attenuation'], v['delay_time'], v['data_skip'],
            v['emergency_alert'])

        if cmd != "SIN":
            raise UndenUnexpectedResponseError

        return ok == "OK"

    def get_trunk_info(self, index):
        # TODO
        pass

    def set_trunk_info(self, index, id_search, motorola_status_bit, motorola_end_code,
            edacs_format, i_call, c_ch_only, fleet_map, custom_fleet_map, base_frequency1,
            step1, offset1, base_frequencey2, step2, offset2, base_frequency3, step3, offset3,
            talkgroup_head, talkgroup_tail, talkgroup_lockout_head, talkgroup_lockout_tail):
        # TODO
        pass

    def get_trunk_frequency_info(self, channel_index):
        """
        Get Trunk Frequency Information.

        The returned dict has the following keys:

            frequency
            lcn
            reverse_index
            forward_index
            system_index
            group_index

        This command is only acceptable in Programming Mode.
        """
        cmd, frq, lcn, rev_index, fwd_index, sys_index, grp_index = self._send("TFQ")

        if cmd != "TFQ":
            raise UnidenUnexpectedResultError

        return {
            "frequency": frq,
            "lcn": lcn,
            "reverse_index": rev_index,
            "forward_index": fwd_index,
            "system_index": sys_index,
            "group_index": grp_index
        }

    def set_trunk_frequency_info(self, channel_index, frequency, lcn):
        """
        Set Trunk Frequency Information.

        This command is only acceptable in Programming Mode.
        """
        cmd, ok = self._send("TFQ", channel_index, frequency, lcn)

        if cmd != "TFQ":
            raise UnidenUnexpectedResultError

        return ok == "OK"

    def append_channel_group(self, system_index):
        """
        Append Channel Group to the system found at the given index.

        This command is only acceptable in Programming Mode.
        """
        cmd, group_index = self._send("AGC", system_index)

        if cmd != "AGC":
            raise UnidenUnexpectedResultError

        if group_index == "-1":
            raise UnidenOutOfResourcesError

        return group_index

    def append_talkgroup_id_group(self, system_index):
        """
        Append TGID Group to the system found at the given index.

        This command is only acceptable in Programming Mode.
        """
        cmd, group_index = self._send("AGI", system_index)

        if cmd != "AGI":
            raise UnidenUnexpectedResultError

        if group_index == "-1":
            raise UnidenOutOfResourcesError

        return group_index

    def delete_group(self, group_index):
        """
        Delete a Channel Group or TGID Group.

        This command is only acceptable in Programming Mode.
        """
        cmd, ok = self._send("DGR", idx)

        if cmd != "DGR":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_group_info(self, group_index):
        """
        Get infomation on the Group found at the given group_index.

        The returned dict has the following keys:

            group_type
            group_name
            quick_key
            lockout
            reverse_index
            forward_index
            system_index
            channel_head_index
            channel_tail_index
            group_sequence

        This command is only acceptable in Programming Mode.
        """
        cmd, grp_type, name, quick_key, lout, rev_index, fwd_index, sys_index, chn_head, \
            chn_tail, seq_no = self._send("GIN", group_index)

        if cmd != "GIN":
            raise UnidenUnexpectedResultError

        return {
            "group_type": grp_type,
            "group_name": name,
            "quick_key": quick_key != '.' and int(quick_key) or None,
            "lockout": lout == "1",
            "reverse_index": rev_index != "-1" and int(rev_index) or None,
            "forward_index": fwd_index != "-1" and int(fwd_index) or None,
            "system_index": int(sys_index),
            "channel_head_index": int(chn_head),
            "channel_tail_index": int(chn_tail),
            "group_sequence": int(seq_no)
        }

    def set_group_info(self, index, name, v={}):
        for k in GROUP_DEFAULTS.keys():
            if v.get(k) is None:
                v[k] = GROUP_DEFAULTS[k]

        if v['quick_key'] is None:
            v['quick_key'] = '.'

        cmd, ok = self._send("GIN", index, name, v['quick_key'], v['lockout'])

        if cmd != "GIN":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def append_channel(self, group_index):
        cmd, channel_index = self._send("ACC", group_index)

        if cmd != "ACC":
            raise UnidenUnexpectedResponseError

        return channel_index

    def append_talkgroup_id(self, group_index):
        cmd, index = self._send("ACT", group_index)

        if cmd != "ACT":
            raise UnidenUnexpectedResponseError

        return index

    def delete_channel(self, index):
        cmd, ok = self._send("DCH", index)

        if cmd != "DCH":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_channel_info(self, index):
        cmd, name, frq, stp, mod, ctcss_dcs, tlock, lout, pri, att, alt, rev_index, fwd_index, sys_index, grp_index = \
            self._send("CIN", index)

        if cmd != "CIN":
            raise UnidenUnexpectedResponseError

        return {
            "name": name,
            "frequency": int(frq),
            "search_step": int(stp), # FIXME
            "modulation": mod,
            "ctcss_dcs_mode": int(ctcss_dcs),
            "ctcss_dcs_tone_lockout": tlock == "1",
            "lockout": lout == "1",
            "priority": int(pri),
            "attenuation": att == "1",
            "alert": alt == "1",
            "reverse_index": rev_index != "-1" and int(rev_index) or None,
            "forward_index": fwd_index != "-1" and int(fwd_index) or None,
            "system_index": int(sys_index),
            "group_index": int(grp_index)
        }

    def set_channel_info(self, index, name, frequency, modulation, v={}):
        for k in CHANNEL_DEFAULTS.keys():
            if v.get(k) is None:
                v[k] = CHANNEL_DEFAULTS[k]

        cmd, ok = self._send("CIN", index, name, ("%08d" % frequency), v['search_step'],
            modulation, v['ctcss_dcs_mode'], v['ctcss_dcs_tone_lockout'], v['lockout'],
            v['priority'], v['attenuation'], v['alert'])

        if cmd != "CIN":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_talkgroupid_info(self, index):
        cmd, name, tgid, lout, alt, rev_index, fwd_index, sys_index, grp_index = \
            self._send("TIN", index)

        if cmd != "TIN":
            raise UnidenUnexpectedResponseError

        return {
            "name": name,
            "tgid": tgid,
            "lockout": lout == "1",
            "alert": alt == "1",
            "reverse_index": rev_index,
            "forward_index": fwd_index,
            "system_index": sys_index,
            "group_index": grp_index
        }

    def set_talkgroupid_info(self, name, tgid, lockout=False, alert=False):
        cmd, ok = self._send("TIN", name, tgid, lockout, alert)

        if cmd != "TIN":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_lockout_talkgroupid(self, system_index):
        cmd, tgid = self._send("GLI", system_index)

        if cmd != "GLI":
            raise UnidenUnexpectedResponseError

        return tgid

    def unlock_talkgroupid(self, system_index, tgid):
        cmd, ok = self._send("ULI", system_index, tgid)

        if cmd != "ULI":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def lock_talkgroup_id(self, system_index, tgid):
        cmd, ok = self._send("LOI", system_index, tgid)

        if cmd != "LOI":
            raise UnidenUnexpectedResponzeError

        return ok == "OK"

    def get_reverse_index(self, index):
        cmd, index = self._send("REV", index)

        if cmd != "REV":
            raise UnidenUnexpectedResponseError

        return int(index)

    def get_forward_index(self, index):
        cmd, index = self._send("FWD", index)

        if cmd != "FWD":
            raise UnidenUnexpectedResponseError

        return int(index)

    def get_free_memory(self):
        cmd, free = self._send("RMB")

        if cmd != "RMB":
            raise UnidenUnexpectedResponseError

        return int(free)

    def get_used_memory(self):
        cmd, used = self._send("MEM")

        if cmd != "MEM":
            raise UnidenUnexpectedResponseError

        return int(used)

    ########################################################################
    ##  Search/Close Call Settings
    ########################################################################

    def get_search_settings(self):
        cmd, stp, mod, att, dly, skp, code_srch, scr, rep, max_store = \
            self.__call("SCO")

        if cmd != "SCO":
            raise UnidenUnexpectedResponseError

        return {
            "search_step": int(stp),  # FIXME
            "modulation": mod,
            "attenuation": att == "1",
            "delay_time": dly,
            "data_skip": skp == "1",
            "ctcss_scss_search": code_srch == "1",
            "pager_uhf_tv_screen": scr,  # FIXME
            "repeater_find": rep == "1",
            "max_auto_store": max_store
        }

    get_close_call_settings = get_search_settings

    def set_search_settings(self, search_step, modulation, attenuation, delay_time,
            data_skip, ctcss_scss_search, pager_uhf_tv_screen, repeater_find, max_auto_store):
        cmd, ok = self._send("SCO", search_step, modulation, attenuation, delay_time,
            data_skip, ctcss_scss_search, pager_uhf_tv_screen, repeater_find, max_auto_store)

        if cmd != "SCO":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    set_close_call_settings = set_search_settings

    def get_global_lockout_frequency(self):
        cmd, frequency = self._send("GLF")

        if cmd != "GLF":
            raise UnidenUnexpectedResultError

        return frequency == "-1" and False or frequency

    def unlock_global_lockout(self, frequency):
        cmd, ok = self._send("ULF", frequency)

        if cmd != "ULF":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def lockout_frequency(self, frequency):
        cmd, ok = self._send("LOF", frequency)

        if cmd != "LOF":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_close_call_settings(self):
        cmd, cc_mode, cc_override, alt, cc_band = self._send("CLC")

        # FIXME: make all the others as thorough as this one...
        if cmd != "CLC" or cc_mode != CC_MODE__VALUES or \
                cc_override not in CC_OVERRIDE__VALUES or \
                alt not in ALERT__VALUES or \
                att not in ATTENUATION__VALUES or \
                not re.match("^(%s)$" % "|".join(ATTENUATION__VALUES), cc_band):

            raise UnidenUnexpectedResponseError

        # FIXME fix these values vvv
        return {
            "mode": cc_mode,
            "override": cc_override,
            "alert": alt,
            "band": cc_band
        }

    ########################################################################
    ##  Custom Search Settings
    ########################################################################

    def get_custom_search_group(self):
        # FIXME
        cmd, value = self._send("CSG")

        if cmd != "CSG":
            raise UnidenUnexpectedResponseError

        return value

    def set_custom_search_group(self, setting):
        # FIXME
        cmd, ok = self._send("CSG", setting)

        if cmd != "CSG":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_custom_search_settings(self, search_index):
        cmd, name, limit_l, limit_h, stp, mod, att, dly, skp = self._send("CSP")

        if cmd != "CSP":
            raise UnidenUnexpectedResponseError

        return {
            "name": name,
            "lower_limit": limit_l,
            "upper_limit": limit_h,
            "search_step": int(stp),
            "modulation": mod,
            "attenuation": att == "1",
            "delay_time": dly,
            "data_skip": skp == "1"
        }

    def set_custom_search_settings(self, name, lower_limit, upper_limit, search_step,
            modulation, attenuation, delay_time, data_skip):
        cmd, ok = self._send("CSP", name, lower_limit, upper_limit, search_step,
            modulation, attenuation, delay_time, data_skip)

        if cmd != "CSP":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    ########################################################################
    ##  Weather Settings
    ########################################################################

    def get_weather_priority_setting(self):
        cmd, priority = self._send("WPR")

        if cmd != "WPR" or priority not in WEATHER_PRIORITY__VALUES:
            raise UnidenUnexpectedResponseError

        return priority

    def set_weather_priority_setting(self, priority):
        if priority not in WEATHER_PRIORITY__VALUES:
            raise ValueError

        cmd, ok = self._send("WPR", priority)

        if cmd != "WPR":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    def get_same_group_settings(self, same_index):
        cmd, same_index, name, fips1, fips2, fips3, fips4, fips5, fips6, fips7, fips8 = \
            self._send("SGB", same_index)

        if cmd != "SGP":
            raise UnidenUnexpectedResponseError

        return {
            "name": name,
            "fips1": fips1,
            "fips2": fips2,
            "fips3": fips3,
            "fips4": fips4,
            "fips5": fips5,
            "fips6": fips6,
            "fips7": fips7,
            "fips8": fips8
        }

    def set_same_group_settings(self, same_index, name, fips1, fips2, fips3, fips4, fips5,
            fips6, fips7, fips8):
        cmd, ok = self._send("SGP", same_index, name, fips1, fips2, fips3,
            fips4, fips5, fips6, fips7, fips8)

    ########################################################################
    ##  Motorola Custom Band Plan
    ########################################################################

    def get_motorola_custom_band_plan_settings(self, index):
        # TODO : this has to be revisited
        cmd, lower1, upper1, step1, offset1, lower2, upper2, step2, offset2, lower3, upper3, \
            step3, offset3, lower4, upper4, step4, offset4, lower5, upper5, step5, offset5 = \
            self._send("MCP")

        if cmd != "MCP":
            raise UnidenUnexpectedReponseError

        return {
            "lower1": lower1,
            "upper1": upper1,
            "step1": step1,
            "offset1": offset1,
            "lower2": lower2,
            "upper2": upper2,
            "step2": step2,
            "offset2": offset2,
            "lower3": lower3,
            "upper3": upper3,
            "step3": step3,
            "offset3": offset3,
            "lower4": lower4,
            "upper4": upper4,
            "step4": step4,
            "offset4": offset4,
            "lower5": lower5,
            "upper5": upper5,
            "step5": step5,
            "offset5": offset5
        }

    def set_motorola_custom_band_plan_settings(self, lower1, upper1, step1, offset1,
            lower2, upper2, step2, offset2, lower3, upper3, step3, offset3, lower4,
            upper4, step4, offset4, lower5, upper5, step5, offset5):
        # TODO : this has to be revisited
        cmd, ok = self._send("MCP", lower1, upper1, step1, offset1, lower2, upper2,
            step2, offset2, lower3, upper3, step3, offset3, lower4, upper4, step4,
            offset4, lower5, upper5, step5, offset5)

        if cmd != "MCP":
            raise UnidenUnexpectedResponseError

        return ok == "OK"

    ########################################################################
    ##  Test
    ########################################################################

    def get_window_voltage(self):
        cmd, av, value = self._send("WIN")

        if cmd != "WIN":
            raise UnidenUnexpectedResponseError

        return av, value

    def get_battery_voltage(self):
        cmd, value = self._send("BAV")

        if cmd != "BAV":
            raise UnidenUnexpectedResponseError

        return int(value)

if __name__ == "__main__":
    print("compiled to bytecode!")
