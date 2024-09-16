from collections import defaultdict
from pathlib import Path
from typing import Optional

import pytest

from nextline import Nextline, events
from nextline.plugin.spec import Context, hookimpl

from .funcs import extract_comment


async def test_run(statement: str) -> None:
    nextline = Nextline(statement, trace_threads=True, trace_modules=True)
    assert nextline.state == 'created'
    plugin = Plugin()
    nextline.register(plugin=plugin)
    async with nextline:
        assert nextline.state == 'initialized'
        await run(nextline)

    assert nextline.state == 'closed'
    plugin.assert_events()


async def run(nextline: Nextline) -> None:
    async with nextline.run_session():
        pass
    assert not nextline.format_exception()
    nextline.result()
    await nextline.reset()
    async with nextline.run_session():
        pass
    assert not nextline.format_exception()
    nextline.result()


class Plugin:
    def __init__(self) -> None:
        self._events = defaultdict[type[events.Event], list[events.Event]](list)

    @hookimpl
    async def on_start_run(self, event: events.OnStartRun) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_end_run(self, event: events.OnEndRun) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_start_trace(self, event: events.OnStartTrace) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_end_trace(self, event: events.OnEndTrace) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_start_trace_call(self, event: events.OnStartTraceCall) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_end_trace_call(self, event: events.OnEndTraceCall) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_start_cmdloop(self, event: events.OnStartCmdloop) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_end_cmdloop(self, event: events.OnEndCmdloop) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_start_prompt(
        self, context: Context, event: events.OnStartPrompt
    ) -> None:
        self._events[event.__class__].append(event)
        nextline = context.nextline
        command = 'next'
        if event.event == 'line':
            line = nextline.get_source_line(
                line_no=event.line_no, file_name=event.file_name
            )
            command = find_command(line) or command
        await nextline.send_pdb_command(
            command=command,
            prompt_no=event.prompt_no,
            trace_no=event.trace_no,
        )

    @hookimpl
    async def on_end_prompt(self, context: Context, event: events.OnEndPrompt) -> None:
        self._events[event.__class__].append(event)

    @hookimpl
    async def on_write_stdout(self, event: events.OnWriteStdout) -> None:
        self._events[event.__class__].append(event)
        assert 'here' in event.text

    def assert_events(self) -> None:
        # Assert only the number of events
        assert len(self._events[events.OnStartRun]) == 2
        assert len(self._events[events.OnEndRun]) == 2
        assert len(self._events[events.OnStartTrace]) == 10
        assert len(self._events[events.OnEndTrace]) == 10
        assert len(self._events[events.OnStartTraceCall]) >= 356
        assert len(self._events[events.OnEndTraceCall]) >= 356
        assert len(self._events[events.OnStartCmdloop]) == 116
        assert len(self._events[events.OnEndCmdloop]) == 116
        assert len(self._events[events.OnStartPrompt]) == 116
        assert len(self._events[events.OnEndPrompt]) == 116
        assert len(self._events[events.OnWriteStdout]) == 2


def find_command(line: str) -> Optional[str]:
    '''The Pdb command indicated in a comment

    >>> find_command('func()  # step')
    'step'
    '''
    import re

    if not (comment := extract_comment(line)):
        return None
    regex = re.compile(r'^# +(\w+) *$')
    match = regex.search(comment)
    if match:
        return match.group(1)
    return None


@pytest.fixture
def statement(script_dir : str, monkey_patch_syspath: None) -> str:
    del monkey_patch_syspath
    return (Path(script_dir) / 'script.py').read_text()


@pytest.fixture
def monkey_patch_syspath(monkeypatch: pytest.MonkeyPatch, script_dir: str) -> None:
    monkeypatch.syspath_prepend(script_dir)


@pytest.fixture
def script_dir() -> str:
    return str(Path(__file__).resolve().parent / 'example')
