import time

from nextline import Nextline


def func():

    time.sleep(0.001)


async def test_one() -> None:
    async with Nextline(func) as nextline:
        async with nextline.run_session():
            async for prompt in nextline.prompts():
                nextline.send_pdb_command('next', prompt.prompt_no, prompt.trace_no)
        nextline.exception()
