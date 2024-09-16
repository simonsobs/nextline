import asyncio
import signal

from nextline import Nextline, events
from nextline.plugin.spec import Context, hookimpl

STATEMENT = '''
import time

time.sleep(100)
'''.lstrip()


async def test_run() -> None:
    nextline = Nextline(STATEMENT)
    nextline.register(plugin=Plugin())
    async with nextline:
        await run(nextline=nextline)


class Plugin:
    def __init__(self) -> None:
        self._events = list[events.Event]()

    @hookimpl
    async def on_start_prompt(
        self, context: Context, event: events.OnStartPrompt
    ) -> None:
        nextline = context.nextline
        await nextline.send_pdb_command(
            command='next', prompt_no=event.prompt_no, trace_no=event.trace_no
        )
        if event.event == 'line' and event.line_no == 3:  # sleep()
            line = nextline.get_source_line(event.line_no, event.file_name)
            assert 'time.sleep(100)' in line
            await asyncio.sleep(0.005)
            await nextline.kill()

    @hookimpl
    async def on_end_run(self, event: events.OnEndRun) -> None:
        assert not event.raised

    @hookimpl
    async def on_finished(self, context: Context) -> None:
        assert (exited_process := context.exited_process) is not None
        assert exited_process.process.exitcode == -signal.SIGKILL


async def run(nextline: Nextline) -> None:
    async with nextline.run_session():
        pass
    assert not nextline.format_exception()
    ret = nextline.result()
    assert ret is None

