import asyncio
from logging import getLogger
from typing import Any, Optional

from transitions import EventData

from nextline.plugin import Context
from nextline.spawned import Command
from nextline.types import ResetOptions

from .factory import build_state_machine


class Machine:
    '''The finite state machine of the nextline states.'''

    def __init__(self, context: Context) -> None:
        self._context = context
        self._hook = context.hook
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
        await self._hook.ahook.on_change_state(
            context=self._context, state_name=self.state  # type: ignore
        )

    async def on_exit_created(self, _: EventData) -> None:
        await self._hook.ahook.start(context=self._context)

    async def on_enter_initialized(self, _: EventData) -> None:
        self._context.run_arg = self._hook.hook.compose_run_arg(context=self._context)
        await self._hook.ahook.on_initialize_run(context=self._context)

    async def on_enter_running(self, _: EventData) -> None:
        self.run_finished = asyncio.Event()
        run_started = asyncio.Event()

        async def run() -> None:
            async with self._hook.awith.run(context=self._context):
                run_started.set()
            self._context.run_arg = None
            await self.finish()  # type: ignore
            self.run_finished.set()

        self._task = asyncio.create_task(run())
        await run_started.wait()

    async def send_command(self, command: Command) -> None:
        await self._hook.ahook.send_command(context=self._context, command=command)

    async def interrupt(self) -> None:
        await self._hook.ahook.interrupt(context=self._context)

    async def terminate(self) -> None:
        await self._hook.ahook.terminate(context=self._context)

    async def kill(self) -> None:
        await self._hook.ahook.kill(context=self._context)

    async def on_close_while_running(self, _: EventData) -> None:
        await self.run_finished.wait()

    async def wait(self) -> None:
        await self.run_finished.wait()
    
    async def on_enter_finished(self, _: EventData) -> None:
        await self._hook.ahook.on_finished(context=self._context)

    async def on_exit_finished(self, _: EventData) -> None:
        await self._task

    def format_exception(self) -> Optional[str]:
        return self._hook.hook.format_exception(context=self._context)

    def result(self) -> Any:
        return self._hook.hook.result(context=self._context)

    async def on_enter_closed(self, _: EventData) -> None:
        await self._hook.ahook.close(context=self._context)

    async def on_reset(self, event: EventData) -> None:
        logger = getLogger(__name__)
        if args := list(event.args):
            logger.warning(f'Unexpected args: {args!r}')
        kwargs = event.kwargs
        reset_options: ResetOptions = kwargs.pop('reset_options')
        if kwargs:
            logger.warning(f'Unexpected kwargs: {kwargs!r}')
        await self._hook.ahook.reset(context=self._context, reset_options=reset_options)

    async def __aenter__(self) -> 'Machine':
        await self.initialize()  # type: ignore
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore
        del exc_type, exc_value, traceback
        await self.close()  # type: ignore
