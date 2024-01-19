import time

from nextline import Nextline
from nextline.plugin.spec import Context, hookimpl
from nextline.spawned import OnStartPrompt


def func():
    time.sleep(0.001)


class Plugin:
    @hookimpl
    async def on_start_prompt(self, context: Context, event: OnStartPrompt) -> None:
        await context.nextline.send_pdb_command('next', event.prompt_no, event.trace_no)


async def test_one() -> None:
    nextline = Nextline(func, trace_modules=True)
    assert nextline.register(Plugin())
    async with nextline:
        async with nextline.run_session():
            pass
        nextline.exception()
