from nextline import Nextline, events
from nextline.plugin.spec import Context, hookimpl

STATEMENT = '''
def f():
    raise RuntimeError('foo')


f()
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

    @hookimpl
    async def on_end_run(self, event: events.OnEndRun) -> None:
        assert 'RuntimeError' in event.raised

    @hookimpl
    async def on_finished(self, context: Context) -> None:
        assert (exited_process := context.exited_process) is not None
        assert (returned := exited_process.returned) is not None
        assert (fmt_exc := returned.fmt_exc) is not None
        assert 'RuntimeError' in fmt_exc


async def run(nextline: Nextline):
    async with nextline.run_session():
        pass
    fmt_exc = nextline.format_exception()
    assert fmt_exc is not None
    assert 'RuntimeError' in fmt_exc
