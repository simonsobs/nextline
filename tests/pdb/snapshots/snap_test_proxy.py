# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_proxy[asyncio] 1'] = [
    [
        (
            'run_a',
            'call',
            False
        ),
        (
            'a',
            'call',
            False
        ),
        (
            'a',
            'call',
            False
        )
    ],
    [
        (
            'run_a',
            'line',
            False
        ),
        (
            'a',
            'line',
            False
        ),
        (
            'a',
            'exception',
            False
        )
    ],
    [
        (
            'a',
            'return',
            True
        ),
        (
            'a',
            'line',
            False
        ),
        (
            'run_a',
            'return',
            False
        )
    ],
    [
        (
            'a',
            'return',
            False
        )
    ]
]

snapshots['test_proxy[lambda] 1'] = [
    [
        (
            'call_lambda',
            'call',
            False
        )
    ],
    [
        (
            'call_lambda',
            'line',
            False
        )
    ],
    [
        (
            'call_lambda',
            'line',
            False
        )
    ],
    [
        (
            'call_lambda',
            'return',
            False
        )
    ]
]

snapshots['test_proxy[nested-func] 1'] = [
    [
        (
            'subject',
            'call',
            False
        ),
        (
            'f',
            'call',
            False
        ),
        (
            'f',
            'call',
            False
        )
    ],
    [
        (
            'subject',
            'line',
            False
        ),
        (
            'f',
            'line',
            False
        ),
        (
            'f',
            'line',
            False
        )
    ],
    [
        (
            'f',
            'line',
            False
        ),
        (
            'subject',
            'line',
            False
        ),
        (
            'f',
            'line',
            False
        )
    ],
    [
        (
            'f',
            'return',
            False
        ),
        (
            'f',
            'return',
            False
        ),
        (
            'subject',
            'line',
            False
        )
    ],
    [
        (
            'subject',
            'return',
            False
        )
    ]
]

snapshots['test_proxy[simple] 1'] = [
    [
        (
            'f',
            'call',
            False
        )
    ],
    [
        (
            'f',
            'line',
            False
        )
    ],
    [
        (
            'f',
            'line',
            False
        )
    ],
    [
        (
            'f',
            'return',
            False
        )
    ]
]

snapshots['test_proxy[yield] 1'] = [
    [
        (
            'call_gen',
            'call',
            False
        ),
        (
            'gen',
            'call',
            False
        ),
        (
            'gen',
            'call',
            False
        ),
        (
            'gen',
            'call',
            False
        )
    ],
    [
        (
            'call_gen',
            'line',
            False
        ),
        (
            'gen',
            'line',
            False
        ),
        (
            'gen',
            'line',
            False
        ),
        (
            'gen',
            'return',
            False
        )
    ],
    [
        (
            'gen',
            'return',
            False
        ),
        (
            'call_gen',
            'line',
            False
        ),
        (
            'gen',
            'return',
            False
        )
    ],
    [
        (
            'call_gen',
            'line',
            False
        )
    ],
    [
        (
            'call_gen',
            'line',
            False
        )
    ],
    [
        (
            'call_gen',
            'line',
            False
        )
    ],
    [
        (
            'call_gen',
            'exception',
            False
        )
    ],
    [
        (
            'call_gen',
            'return',
            False
        )
    ]
]
