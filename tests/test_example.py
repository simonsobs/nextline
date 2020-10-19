import asyncio
import janus
from functools import partial
from pathlib import Path

import pytest

from nextline import run_pdb
from nextline import control_pdb

##__________________________________________________________________||
_THIS_DIR = Path(__file__).resolve().parent
print(_THIS_DIR)
statement = """
import sys
sys.path.insert(0, "{}")
import script
script.script()
""".format(_THIS_DIR)

commands = [*['n']*3, 's', 'l', 'n', 'l', 'c']

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_run_pdb(event_loop):
    queue_in = janus.Queue()
    queue_out = janus.Queue()
    run_pdb_ = event_loop.run_in_executor(None, partial(run_pdb, statement, queue_in.sync_q, queue_out.sync_q))
    await control_pdb(commands, queue_in.async_q, queue_out.async_q)
    await run_pdb_

##__________________________________________________________________||
