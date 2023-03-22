import asyncio
from typing import Any, Optional

from transitions import EventData

from nextline.context import Context
from nextline.spawned import Command

from .factory import build_state_machine


class Machine:
    '''The finite state machine of the nextline states.'''

    def __init__(self, context: Context):
        self._context = context

        self._machine = build_state_machine(model=self)
        self._machine.after_state_change = self.after_state_change.__name__  # type: ignore

        assert self.state  # type: ignore

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'

    async def after_state_change(self, event: EventData) -> None:
        if event.event and event.event.name in ('interrupt', 'terminate', 'kill'):
            return
        await self._context.state_change(self.state)  # type: ignore

    async def on_enter_initialized(self, _: EventData) -> None:
        await self._context.initialize()

    async def on_enter_running(self, _: EventData) -> None:
        self.run_finished = asyncio.Event()
        run_started = asyncio.Event()

        async def run() -> None:
            async with self._context.run():
                run_started.set()
            # await self._context.finish()
            await self.finish()  # type: ignore
            self.run_finished.set()

        self._task = asyncio.create_task(run())
        await run_started.wait()

    async def send_command(self, command: Command) -> None:
        assert self.is_running()  # type: ignore
        self._context.send_command(command)

    async def on_interrupt(self, _: EventData) -> None:
        self._context.interrupt()

    async def on_terminate(self, _: EventData) -> None:
        self._context.terminate()

    async def on_kill(self, _: EventData) -> None:
        self._context.kill()

    async def wait(self, _: EventData) -> None:
        await self.run_finished.wait()

    async def on_exit_finished(self, _: EventData) -> None:
        await self._task

    def exception(self) -> Optional[BaseException]:
        assert self.is_finished()  # type: ignore
        return self._context.exception()

    def result(self) -> Any:
        assert self.is_finished()  # type: ignore
        return self._context.result()

    async def on_enter_closed(self, _: EventData) -> None:
        await self._context.close()

    async def on_reset(self, event: EventData) -> None:
        await self._context.reset(*event.args, **event.kwargs)

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()
