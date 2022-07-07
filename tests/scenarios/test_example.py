from __future__ import annotations

import asyncio
import dataclasses
from functools import partial
from operator import attrgetter
from itertools import groupby
from collections import Counter
from pathlib import Path
import datetime
from collections import deque

from typing import Optional, Sequence, Set

import pytest

from typing import Dict, Any

from nextline import Nextline
from nextline.utils import agen_with_wait
from nextline.types import RunNo, RunInfo

from .funcs import replace_with_bool


async def test_run(nextline: Nextline, statement: str):
    assert nextline.state == "initialized"

    await asyncio.gather(
        assert_subscriptions(nextline, statement),
        control_execution(nextline),
        run(nextline),
    )

    assert nextline.state == "closed"


async def assert_subscriptions(nextline: Nextline, statement: str):
    await asyncio.gather(
        assert_subscribe_state(nextline),
        assert_subscribe_run_no(nextline),
        assert_subscribe_run_info(nextline, statement),
        assert_subscribe_trace_info(nextline),
        assert_subscribe_prompt_info(nextline),
        # assert_subscribe_stdout(nextline),
    )


async def assert_subscribe_state(nextline: Nextline):
    expected = [
        "initialized",
        "running",
        "finished",
        "initialized",
        "running",
        "finished",
        "closed",
    ]
    actual = [s async for s in nextline.subscribe_state()]
    assert actual == expected


async def assert_subscribe_run_no(nextline: Nextline):
    expected = [1, 2]
    actual = [s async for s in nextline.subscribe_run_no()]
    assert actual == expected


async def assert_subscribe_run_info(nextline: Nextline, statement: str):

    replace: partial[RunInfo] = partial(
        replace_with_bool, fields=("started_at", "ended_at")
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
                result="null",
                ended_at=datetime.datetime.now(),
            ),
            info := RunInfo(
                run_no=RunNo(2),
                state="running",
                script=statement,
                result=None,
                exception=None,
                started_at=datetime.datetime.now(),
            ),
            dataclasses.replace(
                info,
                state="finished",
                result="null",
                ended_at=datetime.datetime.now(),
            ),
        ]
    )

    async for info in nextline.subscribe_run_info():
        expected = expected_list.popleft()
        expected = replace(expected)
        assert expected == replace(info)
    assert not expected_list


async def assert_subscribe_trace_info(nextline: Nextline):
    results = [s async for s in nextline.subscribe_trace_info()]
    assert {1, 2} == {r.run_no for r in results}
    assert {"running": 10, "finished": 10} == Counter(r.state for r in results)

    groupby_state_ = groupby(
        sorted(results, key=attrgetter("state")),
        attrgetter("state"),
    )
    groupby_state = {k: list(v) for k, v in groupby_state_}
    running = groupby_state["running"]
    finished = groupby_state["finished"]

    assert {1, 2, 3, 4, 5} == {r.trace_no for r in running}
    assert {1, 2, 3, 4, 5} == {r.trace_no for r in finished}

    expected = {(1, None), (2, None), (3, None), (1, 1), (1, 2)}
    assert expected == {(r.thread_no, r.task_no) for r in running}
    assert expected == {(r.thread_no, r.task_no) for r in finished}

    assert all([r.started_at for r in running])
    assert not any([r.ended_at for r in running])

    assert all([r.started_at for r in finished])
    assert all([r.ended_at for r in finished])


async def assert_subscribe_prompt_info(nextline: Nextline):
    results = [s async for s in nextline.subscribe_prompt_info()]
    assert {1, 2} == {r.run_no for r in results}

    assert 382 == len(results)

    expected: Dict[Any, int]
    actual: Counter[Any]

    expected = {1: 144, 2: 78, 3: 78, 4: 50, 5: 32}
    actual = Counter(r.trace_no for r in results)
    assert actual == expected

    assert [r.prompt_no for r in results]

    expected = {True: 116, False: 266}
    actual = Counter(r.open for r in results)
    assert actual == expected

    expected = {"line": 306, "return": 44, "call": 22, "exception": 10}
    actual = Counter(r.event for r in results)
    assert actual == expected

    expected = {True: 382}
    actual = Counter(r.file_name is not None for r in results)
    assert actual == expected

    expected = {True: 382}
    actual = Counter(r.line_no is not None for r in results)
    assert actual == expected

    expected = {True: 232, False: 150}
    actual = Counter(r.stdout is not None for r in results)
    assert actual == expected

    expected = {None: 266, "next": 112, "step": 4}
    actual = Counter(r.command for r in results)
    assert actual == expected

    expected = {True: 232, False: 150}
    actual = Counter(r.started_at is not None for r in results)
    assert actual == expected

    expected = {True: 116, False: 266}
    actual = Counter(r.ended_at is not None for r in results)
    assert actual == expected


async def assert_subscribe_stdout(nextline: Nextline):
    # doesn't work without the `-s` option
    run_no = 1
    results = [s async for s in nextline.subscribe_stdout()]
    assert {run_no} == {r.run_no for r in results}

    assert 1 == len(results)

    r0 = results[0]
    assert 1 == r0.trace_no
    assert "here!\n" == r0.text
    assert r0.written_at


async def run(nextline: Nextline):
    await asyncio.sleep(0.01)
    await nextline.run()
    nextline.exception()
    nextline.result()
    await nextline.reset()
    await nextline.run()
    nextline.exception()
    nextline.result()
    await nextline.close()


async def control_execution(nextline: Nextline):
    prev_ids: Set[int] = set()
    agen = agen_with_wait(nextline.subscribe_trace_ids())
    pending: Sequence[asyncio.Future] = ()
    async for ids_ in agen:
        ids = set(ids_)
        new_ids, prev_ids = ids - prev_ids, ids  # type: ignore

        tasks = {
            asyncio.create_task(control_trace(nextline, id_))
            for id_ in new_ids
        }
        _, pending = await agen.asend(tasks)  # type: ignore

    await asyncio.gather(*pending)


async def control_trace(nextline: Nextline, trace_no):
    # print(f"control_trace({trace_no})")
    file_name = ""
    async for s in nextline.subscribe_prompt_info_for(trace_no):
        # await asyncio.sleep(0.01)
        if not s.open:
            continue
        # print(s)
        if not file_name == s.file_name:
            assert s.file_name
            file_name = s.file_name
            assert nextline.get_source(file_name)
        command = "next"
        if s.event == "line":
            line = nextline.get_source_line(
                line_no=s.line_no,
                file_name=s.file_name,
            )
            command = find_command(line) or command
        nextline.send_pdb_command(command, s.prompt_no, trace_no)
        # await asyncio.sleep(0.01)


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
async def nextline(statement):
    async with Nextline(statement) as y:
        yield y


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
