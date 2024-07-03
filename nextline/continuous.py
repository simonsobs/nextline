'''A temporary workaround implementation of non-interactive mode.

The non-interactive mode needs to be properly reimplemented in the trace
function.
'''
import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator

from nextline.events import OnStartPrompt
from nextline.plugin.spec import Context, hookimpl
from nextline.utils.pubsub import PubSubItem

if TYPE_CHECKING:
    from nextline import Nextline


class Continue:
    def __init__(self, pubsub_enabled: PubSubItem[bool]) -> None:
        self._pubsub_enabled = pubsub_enabled

    @hookimpl
    async def on_start_prompt(self, context: Context, event: OnStartPrompt) -> None:
        await context.nextline.send_pdb_command(
            command='continue',
            prompt_no=event.prompt_no,
            trace_no=event.trace_no,
        )

    @hookimpl
    async def on_finished(self, context: Context) -> None:
        context.nextline.unregister(plugin=self)
        await self._pubsub_enabled.publish(False)


class Continuous:
    def __init__(self, nextline: 'Nextline'):
        self._nextline = nextline
        self._pubsub_enabled = PubSubItem[bool]()

    async def start(self) -> None:
        await self._pubsub_enabled.publish(False)

    async def close(self) -> None:
        await self._pubsub_enabled.aclose()

    async def __aenter__(self) -> 'Continuous':
        await self.start()
        return self

    async def __aexit__(self, *_: Any, **__: Any) -> None:
        await self.close()

    async def run_and_continue(self) -> None:
        await self._pubsub_enabled.publish(True)
        self._nextline.register(plugin=Continue(pubsub_enabled=self._pubsub_enabled))
        await self._nextline.run()

    async def run_continue_and_wait(self, started: asyncio.Event) -> None:
        await self._pubsub_enabled.publish(True)
        self._nextline.register(plugin=Continue(pubsub_enabled=self._pubsub_enabled))
        async with self._nextline.run_session():
            started.set()

    @property
    def enabled(self) -> bool:
        return self._pubsub_enabled.latest()

    def subscribe_enabled(self) -> AsyncIterator[bool]:
        return self._pubsub_enabled.subscribe()
