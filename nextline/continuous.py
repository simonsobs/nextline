'''A temporary workaround implementation of non-interactive mode.

The non-interactive mode needs to be properly reimplemented in the trace
function.
'''
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Set

from nextline.utils.pubsub import PubSubItem

if TYPE_CHECKING:
    from nextline import Nextline


class Continuous:
    def __init__(self, nextline: Nextline):
        self._nextline = nextline

        self._pubsub_enabled = PubSubItem[bool]()
        self._tasks: Set[asyncio.Task] = set()

    async def start(self) -> None:
        await self._pubsub_enabled.publish(False)
        self._task = asyncio.create_task(self._monitor_state())

    async def close(self) -> None:
        await self._task
        if self._tasks:
            await asyncio.gather(*self._tasks)
        await self._pubsub_enabled.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()

    async def _monitor_state(self):
        async for state in self._nextline.subscribe_state():
            if state == 'initialized' and self._tasks:
                _, pending = await asyncio.wait(
                    self._tasks, timeout=0.001, return_when=asyncio.FIRST_COMPLETED
                )
                self._tasks.clear()
                self._tasks.update(pending)

    async def run_and_continue(self):
        task = asyncio.create_task(self._run_and_continue())
        self._tasks.add(task)

    async def _run_and_continue(self):
        await self._pubsub_enabled.publish(True)
        try:
            async with self._nextline.run_session():
                async for prompt in self._nextline.prompts():
                    await self._nextline.send_pdb_command(
                        command='continue',
                        prompt_no=prompt.prompt_no,
                        trace_no=prompt.trace_no,
                    )
        finally:
            await self._pubsub_enabled.publish(False)

    @property
    def enabled(self) -> bool:
        return self._pubsub_enabled.latest()

    def subscribe_enabled(self):
        return self._pubsub_enabled.subscribe()
