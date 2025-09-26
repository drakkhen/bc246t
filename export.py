#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import bc246t
import datetime
import json
import sys

from bc246t import SYSTEM_DEFAULTS, GROUP_DEFAULTS, CHANNEL_DEFAULTS
from jsonschema import validate, ValidationError

def main(include_defaults=False):
    i = bc246t.Interface()

    i.enter_program_mode()

    sys_idx = i.get_system_index_head()

    data = {
        'meta': {
            'created_at': datetime.datetime.now().isoformat(),
        },
        'info': {
            'model': i.get_model(),
            'firmware': i.get_firmware_version(),
        },
        'settings': {
            'backlight': i.get_backlight(),
            'battery_save': i.get_battery_savings_mode(),
            'key_beep': i.get_key_beep(),
            'greeting': i.get_greeting(),
            'priority_mode': i.get_priority_mode(),
        },
        'systems': [],
    }

    while sys_idx:
        system = i.get_system_info(sys_idx)

        if system['attenuation'] == '':
            system['attenuation'] = '0'

        system['groups'] = []
        group_idx = system['group_head_index']

        while group_idx:
            group = i.get_group_info(group_idx)

            group['channels'] = []
            channel_idx = group['channel_head_index']

            while channel_idx:
                channel = i.get_channel_info(channel_idx)

                if channel['attenuation'] == '':
                    channel['attenuation'] = '0'

                for _ in ['reverse_index', 'system_index', 'group_index']:
                    channel.pop(_)

                channel_keys = list(channel.keys())
                for k in channel_keys:
                    if k in CHANNEL_DEFAULTS and channel[k] == CHANNEL_DEFAULTS[k] and not include_defaults:
                        channel.pop(k)

                group['channels'].append(channel)
                channel_idx = channel.pop('forward_index')

            for _ in ['reverse_index', 'system_index', 'channel_head_index', 'channel_tail_index']:
                group.pop(_)

            group_keys = list(group.keys())
            for k in group_keys:
                if k in GROUP_DEFAULTS and group[k] == GROUP_DEFAULTS[k] and not include_defaults:
                    group.pop(k)

            system['groups'].append(group)
            group_idx = group.pop('forward_index')

        for _ in ['reverse_index', 'group_head_index', 'group_tail_index']:
            system.pop(_)

        system_keys = list(system.keys())
        for k in system_keys:
            if k in SYSTEM_DEFAULTS and system[k] == SYSTEM_DEFAULTS[k] and not include_defaults:
                system.pop(k)

        data['systems'].append(system)
        sys_idx = system.pop('forward_index')

    i.exit_program_mode()

    validate(instance=data, schema=bc246t.schema)

    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    include_defaults = '--include-defaults' in sys.argv[1:]
    main(include_defaults)
