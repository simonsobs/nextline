from __future__ import annotations

import asyncio
from operator import attrgetter
from itertools import groupby
from collections import Counter
from pathlib import Path
from typing import Optional, Set

import pytest

from typing import Dict, Any

from nextline import Nextline
from nextline.utils import agen_with_wait


@pytest.mark.asyncio
async def test_run(nextline: Nextline):
    assert nextline.state == "initialized"

    await asyncio.gather(
        assert_subscriptions(nextline),
        control_execution(nextline),
        run(nextline),
    )

    assert nextline.state == "closed"


async def assert_subscriptions(nextline: Nextline):
    await asyncio.gather(
        assert_subscribe_state(nextline),
        assert_subscribe_run_no(nextline),
        assert_subscribe_run_info(nextline),
        assert_subscribe_trace_info(nextline),
        assert_subscribe_prompt_info(nextline),
        # assert_subscribe_stdout(nextline),
    )


async def assert_subscribe_state(nextline: Nextline):
    expected = ["initialized", "running", "finished", "closed"]
    actual = [s async for s in nextline.subscribe_state()]
    assert actual == expected


async def assert_subscribe_run_no(nextline: Nextline):
    expected = [1]
    actual = [s async for s in nextline.subscribe_run_no()]
    assert actual == expected


async def assert_subscribe_run_info(nextline: Nextline):
    run_no = 1
    results = [s async for s in nextline.subscribe_run_info()]
    info0, info1 = results
    assert info0.run_no == info1.run_no == run_no
    assert info0.state == "running"
    assert info1.state == "finished"
    assert info0.script
    assert info0.script == info1.script
    assert info0.result is None
    assert info1.result == "null"
    assert info0.exception is None
    assert info1.exception is None
    assert info0.started_at
    assert info0.started_at == info1.started_at
    assert not info0.ended_at
    assert info1.ended_at


async def assert_subscribe_trace_info(nextline: Nextline):
    run_no = 1
    results = [s async for s in nextline.subscribe_trace_info()]
    assert {run_no} == {r.run_no for r in results}
    assert {"running": 5, "finished": 5} == Counter(r.state for r in results)

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
    run_no = 1
    results = [s async for s in nextline.subscribe_prompt_info()]
    assert {run_no} == {r.run_no for r in results}

    assert 191 == len(results)

    expected: Dict[Any, int]
    actual: Counter[Any]

    expected = {1: 72, 2: 39, 3: 39, 4: 25, 5: 16}
    actual = Counter(r.trace_no for r in results)
    assert actual == expected

    assert [r.prompt_no for r in results]

    expected = {True: 58, False: 133}
    actual = Counter(r.open for r in results)
    assert actual == expected

    expected = {"line": 153, "return": 22, "call": 11, "exception": 5}
    actual = Counter(r.event for r in results)
    assert actual == expected

    expected = {True: 191}
    actual = Counter(r.file_name is not None for r in results)
    assert actual == expected

    expected = {True: 191}
    actual = Counter(r.line_no is not None for r in results)
    assert actual == expected

    expected = {True: 116, False: 75}
    actual = Counter(r.stdout is not None for r in results)
    assert actual == expected

    expected = {None: 133, "next": 56, "step": 2}
    actual = Counter(r.command for r in results)
    assert actual == expected

    expected = {True: 116, False: 75}
    actual = Counter(r.started_at is not None for r in results)
    assert actual == expected

    expected = {True: 58, False: 133}
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
    await nextline.close()


async def control_execution(nextline: Nextline):
    prev_ids: Set[int] = set()
    agen = agen_with_wait(nextline.subscribe_trace_ids())
    async for ids_ in agen:
        ids = set(ids_)
        new_ids, prev_ids = ids - prev_ids, ids  # type: ignore

        tasks = {
            asyncio.create_task(control_trace(nextline, id_))
            for id_ in new_ids
        }
        _, pending = await agen.asend(tasks)  # type: ignore

    await asyncio.gather(*pending)


async def control_trace(nextline: Nextline, trace_id):
    # print(f"control_trace({trace_id})")
    file_name = ""
    async for s in nextline.subscribe_prompt_info_for(trace_id):
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
        nextline.send_pdb_command(trace_id, command)
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
