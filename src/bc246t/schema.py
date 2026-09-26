schema = {
    'type': 'object',
    'requried': ['info', 'settings', 'systems'],
    'additionalProperties': False,
    'properties': {
        'meta': {'type': 'object'},
        'info': {
            'type': 'object',
            'required': ['model','firmware'],
            'properties': {
                'model': {'const': 'BC246T'},
                'firmware': {'type': 'string'},
            }
        },
        'settings': {
            'type': 'object',
            'required': ['backlight', 'battery_save', 'key_beep', 'greeting', 'priority_mode'],
            'properties': {
                'backlight': {
                    'type': 'string',
                    'enum': [
                        '10', # 10sec
                        '30', # 30sec
                        'KY', # KEYPRESS
                        'SQ', # SQUELCH
                    ],
                },
                'battery_save': {'type': 'boolean'},
                'key_beep': {'type': 'boolean'},
                'greeting': {
                    'type': 'array',
                    'minItems': 1,
                    'maxItems': 2,
                    'items': {
                        'type': 'string',
                        'maxLength': 16
                    },
                },
                'priority_mode': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 2
                },
            }
        },
        'systems': {
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['system_type', 'name'],
                'properties': {
                    'system_type': {
                        'type': 'string',
                        'enum': [
                            'CNV',  # CONVENTIONAL
                            'M82S', # MOT_800_T2_STD
                            'M82P', # MOT_800_T2_SPL
                            'M92',  # MOT_900_T2
                            'MV2',  # MOT_VHF_T2
                            'MU2',  # MOT_UHF_T2
                            'M81S', # MOT_800_T1_STD
                            'M81P', # MOT_800_T1_SPL
                            'EDN',  # EDACS_NARROW
                            'EDW',  # EDACS_WIDE
                            'EDS',  # EDACS_SCAT
                            'LTR',  # LTR
                            'M82C', # MOT_800_T2_CUS
                            'M81C', # MOT_800_T1_CUS
                        ]
                    },
                    'name': {
                        'type': 'string',
                        'maxLength': 16,
                    },
                    'quick_key': {
                        'type': ['integer', 'null'],
                        'minimum': 1,
                        'maximum': 9,
                    },
                    'hold_time': {
                        'type': 'integer',
                        'minimum': 0,
                        'maximum': 255,
                    },
                    'lockout': {'type': 'boolean'},
                    'attenuation': {'type': 'boolean'},
                    'delay_time': {
                        'type': 'integer',
                        'minimum': 0,
                        'maximum': 5,
                    },
                    'data_skip': {'type': 'boolean'},
                    'emergency_alert': {'type': 'boolean'},
                    'sequence_number': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': 200,
                    },
                    'groups': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'required': ['group_name'],
                            'properties': {
                                'group_type': {
                                    'type': 'string',
                                    'enum': [
                                        'C', # CHANNEL GROUP
                                        'T', # TGID GROUP
                                    ],
                                },
                                'group_name': {
                                    'type': 'string',
                                    'maxLength': 16,
                                },
                                'quick_key': {
                                    'type': ['integer', 'null'],
                                    'minimum': 1,
                                    'maximum': 9,
                                },
                                'lockout': {'type': 'boolean'},
                                'group_sequence': {
                                    'type': 'integer',
                                    'minimum': 0,
                                },
                                'channels': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'required': ['name', 'frequency', 'modulation'],
                                        'properties': {
                                            'name': {
                                                'type': 'string',
                                                'maxLength': 16,
                                            },
                                            'frequency': {
                                                'type': 'number',
                                                'multipleOf': 25,
                                                'oneOf': [
                                                    { # 25.0000 - 54.0000
                                                        'minimum': 250000,
                                                        'maximum': 540000,
                                                    },
                                                    { # 108.0000 - 174.0000
                                                        'minimum': 1080000,
                                                        'maximum': 1740000,
                                                    },
                                                    { # 216.0000 - 225.0000
                                                        'minimum': 2160000,
                                                        'maximum': 2250000,
                                                    },
                                                    { # 400.0000 - 512.0000
                                                        'minimum': 4000000,
                                                        'maximum': 5120000,
                                                    },
                                                    { # 806.0000 - 956.0000
                                                        'minimum': 8060000,
                                                        'maximum': 9560000,
                                                    },
                                                    { # 1240.0000 - 1300.0000
                                                        'minimum': 12400000,
                                                        'maximum': 13000000,
                                                    },
                                                ],
                                            },
                                            'search_step': {
                                                'type': 'integer',
                                                'enum': [
                                                    0,      # AUTO
                                                    500,    # 5k
                                                    625,    # 6.25k
                                                    750,    # 7.5k
                                                    1000,   # 10k
                                                    1250,   # 12.5k
                                                    1500,   # 15k
                                                    2000,   # 20k
                                                    2500,   # 25k
                                                    5000,   # 50k
                                                    10000,  # 100k
                                                ],
                                            },
                                            'modulation': {
                                                'type': 'string',
                                                'enum': [
                                                    'AUTO',
                                                    'FM',
                                                    'NFM',
                                                    'AM',
                                                ],
                                            },
                                            'ctcss_dcs_mode': {
                                                'type': 'integer',
                                                'minimum': 0,
                                                'maximum': 231,
                                            },
                                            'ctcss_dcs_tone_lockout': {'type': 'boolean'},
                                            'lockout': {'type': 'boolean'},
                                            'priority': {
                                                'type': 'integer',
                                                'minimum': 0,
                                                'maximum': 2
                                            },
                                            'attenuation': {'type': 'boolean'},
                                            'alert': {'type': 'boolean'},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
