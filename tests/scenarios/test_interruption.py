from __future__ import annotations

import asyncio
import dataclasses
from functools import partial
from collections import deque
import datetime

import pytest

from nextline import Nextline
from nextline.types import RunNo, RunInfo

from .funcs import replace_with_bool

STATEMENT = """
import time

time.sleep(100)
""".lstrip()


async def test_run(nextline: Nextline, statement: str):
    assert nextline.state == "initialized"

    await asyncio.gather(
        assert_subscriptions(nextline, statement),
        control(nextline),
        run(nextline),
    )
    assert nextline.state == "closed"


async def assert_subscriptions(nextline: Nextline, statement: str):
    await asyncio.gather(
        assert_subscribe_run_info(nextline, statement),
    )


async def assert_subscribe_run_info(nextline: Nextline, statement: str):

    replace: partial[RunInfo] = partial(
        replace_with_bool, fields=("exception", "started_at", "ended_at")
    )

    expected_list = deque(
        [
            info := RunInfo(
                run_no=RunNo(1),
                state="running",
                script=statement,
                result=None,
                exception=None,
                started_at=datetime.datetime.now(),
            ),
            dataclasses.replace(
                info,
                state="finished",
                exception="KeyboardInterrupt",
                ended_at=datetime.datetime.now(),
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
    await nextline.run()
    exc = nextline.exception()
    assert exc
    assert exc.__traceback__  # tblib
    with pytest.raises(KeyboardInterrupt):
        nextline.result()
    await nextline.close()


async def control(nextline: Nextline):
    async for prompt_info in nextline.subscribe_prompt_info():
        if not prompt_info.open:
            continue
        nextline.send_pdb_command(
            "next", prompt_info.prompt_no, prompt_info.trace_no
        )
        if prompt_info.event == "line" and prompt_info.line_no == 3:  # sleep()
            await asyncio.sleep(0.005)
            nextline.interrupt()


@pytest.fixture
async def nextline(statement):
    async with Nextline(statement) as y:
        yield y


@pytest.fixture
def statement():
    return STATEMENT
