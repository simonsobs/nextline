import asyncio
from logging import getLogger
from typing import Any, Optional

import apluggy
from transitions import EventData

from nextline.spawned import Command
from nextline.types import ResetOptions

from .factory import build_state_machine


class Machine:
    '''The finite state machine of the nextline states.'''

    def __init__(self, hook: apluggy.PluginManager) -> None:
        self._hook = hook
        self._machine = build_state_machine(model=self)
        self._machine.after_state_change = self.after_state_change.__name__  # type: ignore
        assert self.state  # type: ignore

    def __repr__(self) -> str:
        # e.g., "<Machine 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'  # type: ignore

    async def after_state_change(self, event: EventData) -> None:
        if not (event.transition and event.transition.dest):
            # internal transition
            return
        await self._hook.ahook.on_change_state(state_name=self.state)  # type: ignore

    async def on_exit_created(self, _: EventData) -> None:
        await self._hook.ahook.start()

    async def on_enter_initialized(self, _: EventData) -> None:
        self._run_arg = self._hook.hook.compose_run_arg()
        await self._hook.ahook.on_initialize_run(run_arg=self._run_arg)

    async def on_enter_running(self, _: EventData) -> None:
        self.run_finished = asyncio.Event()
        run_started = asyncio.Event()

        async def run() -> None:
            async with self._hook.awith.run():
                run_started.set()
            await self.finish()  # type: ignore
            self.run_finished.set()

        self._task = asyncio.create_task(run())
        await run_started.wait()

    async def send_command(self, command: Command) -> None:
        await self._hook.ahook.send_command(command=command)

    async def interrupt(self) -> None:
        await self._hook.ahook.interrupt()

    async def terminate(self) -> None:
        await self._hook.ahook.terminate()

    async def kill(self) -> None:
        await self._hook.ahook.kill()

    async def on_close_while_running(self, _: EventData) -> None:
        await self.run_finished.wait()

    async def wait(self) -> None:
        await self.run_finished.wait()

    async def on_exit_finished(self, _: EventData) -> None:
        await self._task

    def exception(self) -> Optional[BaseException]:
        return self._hook.hook.exception()

    def result(self) -> Any:
        return self._hook.hook.result()

    async def on_enter_closed(self, _: EventData) -> None:
        await self._hook.ahook.close()

    async def on_reset(self, event: EventData) -> None:
        logger = getLogger(__name__)
        if args := list(event.args):
            logger.warning(f'Unexpected args: {args!r}')
        kwargs = event.kwargs
        reset_options: ResetOptions = kwargs.pop('reset_options')
        if kwargs:
            logger.warning(f'Unexpected kwargs: {kwargs!r}')
        await self._hook.ahook.reset(reset_options=reset_options)

    async def __aenter__(self) -> 'Machine':
        await self.initialize()  # type: ignore
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore
        del exc_type, exc_value, traceback
        await self.close()  # type: ignore
