#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import bc246t
import datetime
import json
import os
import sys

from jsonschema import validate, ValidationError

def main(source):
    data = json.loads(open(source).read())
    validate(instance=data, schema=bc246t.schema)

    print('[*] Data is valid.')

    i = bc246t.Interface()

    i.enter_program_mode()
    model = i.get_model()
    firmware = i.get_firmware_version()
    i.exit_program_mode()

    if model != data['info']['model']:
        print(f'[!] Unsupported scanner model: {model}!')
        sys.exit(1)

    if firmware != data['info']['firmware']:
        print(f'[?] Firmware Conflict!')
        print('')
        print(f"    Data firmware:     {data['info']['firmware']}")
        print(f"    Scanner firmware:  {firmware}")
        print('')

        confirmation = input('    Type "YOLO" to continue: ')
        if confirmation.upper() != 'YOLO':
            print('')
            print('[!] Bailing!')
            sys.exit(1)

    skip_file = '.i-know-what-im-doing'

    if not os.path.exists(skip_file):
        print(f'[?] Scanner will be reset to factory settings before being restored!')
        print('')

        confirmation = input('    Type "YES" to continue: ')
        print('')

        if confirmation.upper() != 'YES':
            print('[!] Bailing!')
            sys.exit(1)

        print(f'    (Touch a "{skip_file}" file to skip this next time.)')
        print('')

    i.enter_program_mode()

    print('[*] Resetting scanner to factory settings...')
    i.clear_all_memory()

    print(f"[*] Setting backlight to {data['settings']['backlight']}")
    i.set_backlight(data['settings']['backlight'])

    print(f"[*] Setting battery save to {data['settings']['battery_save']}")
    i.set_battery_savings_mode(data['settings']['battery_save'])

    print(f"[*] Setting key beep to {data['settings']['key_beep']}")
    i.set_key_beep(data['settings']['key_beep'])

    print(f"[*] Setting greeting to {data['settings']['greeting']}")
    l1, l2 = data['settings']['greeting']
    i.set_greeting(l1, l2)

    print(f"[*] Setting priority mode to {data['settings']['priority_mode']}")
    i.set_priority_mode(data['settings']['priority_mode'])

    print('[*] Creating systems:')
    print('')

    system_count = 0
    group_count = 0
    channel_count = 0

    for s in data['systems']:
        print(f"    [{s['name']}]")
        print('')
        system_idx = i.create_system(s['system_type'])
        system_count += 1

        s['quick_key'] = system_count < 10 and system_count or None
        s['sequence_number'] = system_count

        v = {}
        for k in ['quick_key', 'hold_time', 'lockout', 'attenuation', 'delay_time', 'data_skip', 'emergency_alert']:
            v[k] = s.get(k)

        i.set_system_info(system_idx, s['name'], v)

        system_group_count = 0

        for g in s['groups']:
            print(f"        {g['group_name']}:")
            print('')
            group_idx = i.append_channel_group(system_idx)
            group_count += 1
            system_group_count += 1

            g['quick_key'] = system_group_count < 10 and system_group_count or None
            g['group_sequence'] = group_count

            v = {}
            for k in ['quick_key', 'lockout']:
                v[k] = g.get(k)

            i.set_group_info(group_idx, g['group_name'], v)

            for c in g['channels']:
                print(f"            {c['name']:20} {c['frequency']/10000:.5f} {c['modulation']}")
                channel_idx = i.append_channel(group_idx)
                channel_count += 1

                v = {}
                for k in ['search_step', 'ctcss_dcs_mode', 'ctcss_dcs_tone_lockout', 'lockout', 'priority', 'attenuation', 'alert']:
                    v[k] = c.get(k)

                i.set_channel_info(channel_idx, c['name'], c['frequency'], c['modulation'], v)

            print('')

    i.push_key('S')
    i.exit_program_mode()

    print(f"[*] Created {system_count} systems, {group_count} groups, and {channel_count} channels!")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'usage: {sys.argv[0]} <data_file>')
        sys.exit(-1)

    main(sys.argv[1])
