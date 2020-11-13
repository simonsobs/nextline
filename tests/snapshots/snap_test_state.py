# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_state 1'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': False
        },
        123: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 2'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': True
        },
        123: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 3'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': False
        },
        123: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 4'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': False
        },
        123: {
            'finished': False,
            'prompting': True
        }
    }
}

snapshots['test_state 5'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': False
        },
        123: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 6'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': True
        },
        123: {
            'finished': False,
            'prompting': False
        }
    },
    2222222: {
        None: {
            'finished': False,
            'prompting': True
        },
        124: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 7'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': False
        },
        123: {
            'finished': False,
            'prompting': False
        }
    },
    2222222: {
        None: {
            'finished': False,
            'prompting': True
        },
        124: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 8'] = {
    1111111: {
        None: {
            'finished': False,
            'prompting': False
        },
        123: {
            'finished': False,
            'prompting': False
        }
    },
    2222222: {
        None: {
            'finished': False,
            'prompting': False
        },
        124: {
            'finished': False,
            'prompting': False
        }
    }
}

snapshots['test_state 9'] = {
    1111111: {
        None: {
            'finished': True,
            'prompting': False
        },
        123: {
            'finished': True,
            'prompting': False
        }
    },
    2222222: {
        None: {
            'finished': True,
            'prompting': False
        },
        124: {
            'finished': True,
            'prompting': False
        }
    }
}
