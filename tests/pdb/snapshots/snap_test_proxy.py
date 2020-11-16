# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_sys_settrace 1'] = [
    [
        (
            'subject',
            'call',
            None
        ),
        (
            'f',
            'call',
            None
        ),
        (
            'f',
            'call',
            None
        )
    ],
    [
        (
            'subject',
            'line',
            None
        ),
        (
            'f',
            'line',
            None
        ),
        (
            'f',
            'line',
            None
        )
    ],
    [
        (
            'f',
            'line',
            None
        ),
        (
            'subject',
            'line',
            None
        ),
        (
            'f',
            'line',
            None
        )
    ],
    [
        (
            'f',
            'return',
            0
        ),
        (
            'f',
            'return',
            0
        ),
        (
            'subject',
            'line',
            None
        )
    ],
    [
        (
            'subject',
            'return',
            None
        )
    ]
]
