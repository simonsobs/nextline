import asyncio
from pathlib import Path
from typing import Optional, Set

import pytest

from nextline import Nextline
from nextline.utils import agen_with_wait


@pytest.mark.asyncio
async def test_run(nextline: Nextline):
    assert nextline.state == "initialized"

    await asyncio.gather(
        subscribe_state(nextline),
        control_execution(nextline),
        run(nextline),
    )

    assert nextline.state == "closed"


async def subscribe_state(nextline: Nextline):
    return [s async for s in nextline.subscribe_state()]


async def run(nextline: Nextline):
    await asyncio.sleep(0.01)
    await nextline.run()
    nextline.exception()
    nextline.result()
    await nextline.close()


async def control_execution(nextline: Nextline):
    prev_ids: Set[int] = set()
    agen = agen_with_wait(nextline.subscribe_trace_ids())
    async for ids_ in agen:
        ids = set(ids_)
        new_ids, prev_ids = ids - prev_ids, ids

        tasks = {
            asyncio.create_task(control_trace(nextline, id_))
            for id_ in new_ids
        }
        _, pending = await agen.asend(tasks)

    await asyncio.gather(*pending)


async def control_trace(nextline: Nextline, trace_id):
    # print(f"control_trace({trace_id})")
    file_name = ""
    async for s in nextline.subscribe_prompting(trace_id):
        # print(s)
        if not file_name == s.file_name:
            file_name = s.file_name
            assert nextline.get_source(file_name)
        if s.prompting:
            command = "next"
            if s.trace_event == "line":
                line = nextline.get_source_line(
                    line_no=s.line_no,
                    file_name=s.file_name,
                )
                command = find_command(line) or command
            nextline.send_pdb_command(trace_id, command)


def find_command(line: str) -> Optional[str]:
    """The Pdb command indicated in a comment

    For example, returns "step" for the line "func()  # step"
    """
    import re

    if not (comment := extract_comment(line)):
        return None
    regex = re.compile(r"^# +(\w+) *$")
    match = regex.search(comment)
    if match:
        return match.group(1)
    return None


def extract_comment(line: str) -> Optional[str]:
    import io
    import tokenize

    comments = [
        val
        for type, val, *_ in tokenize.generate_tokens(
            io.StringIO(line).readline
        )
        if type == tokenize.COMMENT
    ]
    if comments:
        return comments[0]
    return None


@pytest.fixture
def nextline(statement):
    return Nextline(statement)


@pytest.fixture
def statement(script_dir, monkey_patch_syspath):
    del monkey_patch_syspath
    return Path(script_dir).joinpath("script.py").read_text()


@pytest.fixture
def monkey_patch_syspath(monkeypatch, script_dir):
    monkeypatch.syspath_prepend(script_dir)
    yield


@pytest.fixture
def script_dir():
    return str(Path(__file__).resolve().parent)
