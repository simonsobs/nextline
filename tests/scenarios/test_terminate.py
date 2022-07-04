from __future__ import annotations

import asyncio
import pytest

from nextline import Nextline

STATEMENT = """
import time

time.sleep(100)
""".lstrip()


async def test_run(nextline: Nextline):
    assert nextline.state == "initialized"

    await asyncio.gather(
        control(nextline),
        run(nextline),
    )
    assert nextline.state == "closed"


async def run(nextline: Nextline):
    await asyncio.sleep(0.01)
    await nextline.run()
    exc = nextline.exception()
    assert exc is None
    ret = nextline.result()
    assert ret is None
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
            nextline.terminate()


@pytest.fixture
async def nextline(statement):
    async with Nextline(statement) as y:
        yield y


@pytest.fixture
def statement():
    return STATEMENT
