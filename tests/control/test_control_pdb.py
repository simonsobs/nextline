import pytest
from unittest.mock import AsyncMock

from nextline import control_pdb

##__________________________________________________________________||
commands = ['list', 'next', 'step', 'continue']

##__________________________________________________________________||
output = """
> <string>(2)<module>()
(Pdb)
> <string>(3)<module>()
(Pdb)
"""
output = [l + ('' if '(Pdb)' == l else '\n') for l in output.strip().split('\n')]
output += [None]

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_control_pdb(snapshot):
    queue_in = AsyncMock()
    queue_out = AsyncMock()
    queue_out.get.side_effect = output
    await control_pdb(commands, queue_in, queue_out)
    snapshot.assert_match(queue_in.put.call_args_list)

##__________________________________________________________________||
