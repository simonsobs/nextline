from nextline import Nextline

SOURCE = '''
import time
time.sleep(0.001)
'''.strip()


async def test_one() -> None:
    async with Nextline(SOURCE) as nextline:
        async with nextline.run_session():
            async for prompt in nextline.prompts():
                nextline.send_pdb_command('next', prompt.prompt_no, prompt.trace_no)
        nextline.exception()
