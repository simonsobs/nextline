from __future__ import annotations

import asyncio
import dataclasses
import datetime
from collections import deque
from functools import partial

import pytest

from nextline import Nextline
from nextline.types import RunInfo, RunNo

from .funcs import replace_with_bool

STATEMENT = '''
def f():
    raise RuntimeError('foo')


f()
'''.lstrip()


async def test_run(nextline: Nextline, statement: str):
    assert nextline.state == 'initialized'

    await asyncio.gather(
        assert_subscriptions(nextline, statement),
        control(nextline),
        run(nextline),
    )
    assert nextline.state == 'closed'


async def assert_subscriptions(nextline: Nextline, statement: str):
    await asyncio.gather(
        assert_subscribe_run_info(nextline, statement),
    )


async def assert_subscribe_run_info(nextline: Nextline, statement: str):
    replace: partial[RunInfo] = partial(
        replace_with_bool, fields=('exception', 'started_at', 'ended_at')
    )

    expected_list = deque(
        [
            info := RunInfo(
                run_no=RunNo(1),
                state='initialized',
                script=statement,
                result=None,
                exception=None,
            ),
            info := dataclasses.replace(
                info,
                state='running',
                started_at=datetime.datetime.utcnow(),
            ),
            dataclasses.replace(
                info,
                state='finished',
                result='null',
                exception='RuntimeError',
                ended_at=datetime.datetime.utcnow(),
            ),
        ]
    )

    async for info in nextline.subscribe_run_info():
        expected = expected_list.popleft()
        if expected.exception:
            assert info.exception
            assert expected.exception in info.exception
        assert replace(expected) == replace(info)
    assert not expected_list


async def run(nextline: Nextline):
    await asyncio.sleep(0.01)
    async with nextline.run_session():
        pass
    exc = nextline.exception()
    assert exc
    assert exc.__traceback__  # tblib
    with pytest.raises(RuntimeError):
        nextline.result()
    await nextline.close()


async def control(nextline: Nextline):
    async for prompt_info in nextline.subscribe_prompt_info():
        if not prompt_info.open:
            continue
        await nextline.send_pdb_command(
            'next', prompt_info.prompt_no, prompt_info.trace_no
        )


@pytest.fixture
async def nextline(statement):
    async with Nextline(statement) as y:
        yield y


@pytest.fixture
def statement():
    return STATEMENT
