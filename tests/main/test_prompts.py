import asyncio

from nextline import Nextline

SOURCE = '''
import time
time.sleep(0.001)
'''.strip()


async def test_one() -> None:
    async with Nextline(SOURCE) as nextline:
        task = asyncio.create_task(nextline.run())
        async for prompt in nextline.prompts():
            nextline.send_pdb_command('next', prompt.prompt_no, prompt.trace_no)
        await task
        nextline.exception()
