import time

from nextline import InitOptions, Nextline


def func():
    time.sleep(0.001)


async def test_one() -> None:
    init_options = InitOptions(statement=func)
    async with Nextline(init_options=init_options) as nextline:
        async with nextline.run_session():
            async for prompt in nextline.prompts():
                await nextline.send_pdb_command(
                    'next', prompt.prompt_no, prompt.trace_no
                )
        nextline.exception()


async def test_close_while_running() -> None:
    init_options = InitOptions(statement=func)
    async with Nextline(init_options=init_options) as nextline:
        await nextline.run()
        async for prompt in nextline.prompts():
            await nextline.send_pdb_command('next', prompt.prompt_no, prompt.trace_no)
