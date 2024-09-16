import time

from nextline import Nextline


def func() -> None:
    time.sleep(0.001)


async def test_one() -> None:
    async with Nextline(func) as nextline:
        async with nextline.run_session():
            async for prompt in nextline.prompts():
                await nextline.send_pdb_command(
                    'next', prompt.prompt_no, prompt.trace_no
                )
        assert not nextline.format_exception()


async def test_close_while_running() -> None:
    async with Nextline(func) as nextline:
        await nextline.run()
        async for prompt in nextline.prompts():
            await nextline.send_pdb_command('next', prompt.prompt_no, prompt.trace_no)
