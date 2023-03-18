import asyncio
from typing import Any, Optional

from transitions import EventData

from nextline.context import Context

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

    async def after_state_change(self, _: EventData) -> None:
        await self._context.state_change(self.state)  # type: ignore

    async def on_enter_initialized(self, _: EventData) -> None:
        await self._context.initialize()

    async def on_enter_running(self, _: EventData) -> None:
        self._event_finished = asyncio.Event()
        await self._context.run()

        async def run() -> None:
            await self._context.finish()
            await self.finish()  # type: ignore
            self._event_finished.set()

        self._task = asyncio.create_task(run())

    def send_pdb_command(self, command: str, prompt_no: int, trace_no: int) -> None:
        assert self.is_running()  # type: ignore
        self._context.send_pdb_command(command, prompt_no, trace_no)

    async def interrupt(self) -> None:
        assert self.is_running()  # type: ignore
        self._context.interrupt()

    async def terminate(self) -> None:
        assert self.is_running()  # type: ignore
        self._context.terminate()

    async def kill(self) -> None:
        assert self.is_running()  # type: ignore
        self._context.kill()

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
