import time

from nextline import Nextline
from nextline.plugin.spec import hookimpl
from nextline.spawned import OnStartPrompt


def func():
    time.sleep(0.001)


class Plugin:
    @hookimpl
    def init(self, nextline: Nextline) -> None:
        self._nextline = nextline

    @hookimpl
    async def on_start_prompt(self, event: OnStartPrompt) -> None:
        await self._nextline.send_pdb_command('next', event.prompt_no, event.trace_no)


async def test_one() -> None:
    nextline = Nextline(func, trace_modules=True)
    assert nextline.register(Plugin())
    async with nextline:
        async with nextline.run_session():
            pass
        nextline.exception()
