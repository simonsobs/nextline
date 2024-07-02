import asyncio
from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any, Optional, Protocol, TypeAlias

from transitions import EventData
from transitions.extensions.asyncio import AsyncMachine

from nextline.plugin import Context
from nextline.spawned import Command
from nextline.types import ResetOptions

from .config import CONFIG

TriggerNoArg: TypeAlias = Callable[[], Coroutine[None, None, bool]]


class Reset(Protocol):
    def __call__(self, reset_options: ResetOptions) -> Coroutine[None, None, bool]:
        ...


class Model:
    '''The model of the transitions AsyncMachine.'''

    state: str
    initialize: TriggerNoArg
    run: TriggerNoArg
    finish: TriggerNoArg
    reset: Reset
    close: TriggerNoArg

    def __init__(self, context: Context) -> None:
        self._context = context
        self._hook = context.hook
        self._machine = AsyncMachine(model=self, **CONFIG)  # type: ignore
        self._machine.after_state_change = self.after_state_change.__name__  # type: ignore
        self._logger = getLogger(__name__)

    def __repr__(self) -> str:
        # e.g., "<Model 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'

    async def after_state_change(self, event: EventData) -> None:
        if not (event.transition and event.transition.dest):
            # Internal transition
            return
        await self._hook.ahook.on_change_state(
            context=self._context, state_name=self.state
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
            try:
                async with self._hook.awith.run(context=self._context):
                    run_started.set()
            except BaseException:
                self._logger.exception('')
                raise
            finally:
                run_started.set()  # Ensure to unblock the await
                self._context.run_arg = None
                try:
                    await self.finish()
                except BaseException:
                    self._logger.exception('')
                    raise
                finally:
                    self.run_finished.set()

        self._task = asyncio.create_task(run())
        await run_started.wait()

    async def on_close_while_running(self, _: EventData) -> None:
        await self.run_finished.wait()

    async def wait(self) -> None:
        await self.run_finished.wait()

    async def on_enter_finished(self, _: EventData) -> None:
        await self._hook.ahook.on_finished(context=self._context)

    async def on_exit_finished(self, _: EventData) -> None:
        await self._task

    async def on_enter_closed(self, _: EventData) -> None:
        await self._hook.ahook.close(context=self._context)

    async def on_reset(self, event: EventData) -> None:
        if args := list(event.args):
            self._logger.warning(f'Unexpected args: {args!r}')
        kwargs = event.kwargs
        reset_options: ResetOptions = kwargs.pop('reset_options')
        if kwargs:
            self._logger.warning(f'Unexpected kwargs: {kwargs!r}')
        await self._hook.ahook.reset(context=self._context, reset_options=reset_options)

    async def __aenter__(self) -> 'Model':
        await self.initialize()
        return self

    async def __aexit__(self, *_: Any, **__: Any) -> None:
        await self.close()


class Machine:
    '''The interface to the finite state machine.'''

    def __init__(self, context: Context) -> None:
        self._context = context
        self._hook = context.hook
        self._model = Model(context=context)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self._model!r}>'

    @property
    def state(self) -> str:
        return self._model.state

    async def initialize(self) -> bool:
        return await self._model.initialize()

    async def run(self) -> bool:
        return await self._model.run()

    async def finish(self) -> bool:
        return await self._model.finish()

    async def reset(self, reset_options: ResetOptions) -> bool:
        return await self._model.reset(reset_options=reset_options)

    async def close(self) -> bool:
        return await self._model.close()

    async def send_command(self, command: Command) -> None:
        await self._hook.ahook.send_command(context=self._context, command=command)

    async def interrupt(self) -> None:
        await self._hook.ahook.interrupt(context=self._context)

    async def terminate(self) -> None:
        await self._hook.ahook.terminate(context=self._context)

    async def kill(self) -> None:
        await self._hook.ahook.kill(context=self._context)

    async def wait(self) -> None:
        await self._model.wait()

    def format_exception(self) -> Optional[str]:
        return self._hook.hook.format_exception(context=self._context)

    def result(self) -> Any:
        return self._hook.hook.result(context=self._context)

    async def __aenter__(self) -> 'Machine':
        await self._model.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self._model.__aexit__(*args, **kwargs)
