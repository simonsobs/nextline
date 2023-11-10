import asyncio
from collections.abc import AsyncIterator

import pytest

from nextline import InitOptions, Nextline, Statement

STATEMENT = """
import time

time.sleep(0.01)
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
    async with nextline.run_session():
        pass
    nextline.exception()
    nextline.result()
    await nextline.close()


async def control(nextline: Nextline):
    async for prompt_info in nextline.subscribe_prompt_info():
        if not prompt_info.open:
            continue
        await nextline.send_pdb_command(
            "next", prompt_info.prompt_no, prompt_info.trace_no
        )


@pytest.fixture
async def nextline(statement: Statement) -> AsyncIterator[Nextline]:
    init_options = InitOptions(statement=statement)
    async with Nextline(init_options=init_options) as y:
        yield y


@pytest.fixture
def statement():
    return STATEMENT
