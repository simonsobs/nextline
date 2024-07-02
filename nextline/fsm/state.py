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
    def __call__(self, *, reset_options: ResetOptions) -> Coroutine[None, None, bool]:
        ...


class Callback:
    def __init__(self, context: Context, machine: 'Imp') -> None:
        self._context = context
        self._hook = context.hook
        self._machine = machine
        self._logger = getLogger(__name__)

    async def on_change_state(self, state_name: str) -> None:
        await self._hook.ahook.on_change_state(
            context=self._context, state_name=state_name
        )

    async def start(self) -> None:
        await self._hook.ahook.start(context=self._context)

    async def initialize_run(self) -> None:
        self._context.run_arg = self._hook.hook.compose_run_arg(context=self._context)
        await self._hook.ahook.on_initialize_run(context=self._context)

    async def start_run(self) -> None:
        self._run_finished = asyncio.Event()
        started = asyncio.Event()

        async def _run() -> None:
            try:
                async with self._hook.awith.run(context=self._context):
                    started.set()
            except BaseException:
                self._logger.exception('')
                raise
            finally:
                started.set()  # Ensure to unblock the await
                self._context.run_arg = None
                try:
                    await self._machine.finish()
                except BaseException:
                    self._logger.exception('')
                    raise
                finally:
                    self._run_finished.set()

        self._task_run = asyncio.create_task(_run())
        await started.wait()

    async def wait_for_run_finish(self) -> None:
        await self._run_finished.wait()

    async def finish(self) -> None:
        await self._hook.ahook.on_finished(context=self._context)

    async def on_exit_finished(self) -> None:
        await self._task_run

    async def close(self) -> None:
        await self._hook.ahook.close(context=self._context)

    async def reset(self, reset_options: ResetOptions) -> None:
        await self._hook.ahook.reset(context=self._context, reset_options=reset_options)


class StateMachine:
    '''The finite state machine.

    This class is the model object of `AsyncMachine` from `transitions`.
    '''

    # Types of objects that will be set by AsyncMachine
    state: str
    initialize: TriggerNoArg
    run: TriggerNoArg
    finish: TriggerNoArg
    reset: Reset
    close: TriggerNoArg

    def __init__(self, callback: Callback) -> None:
        self._callback = callback
        self._machine = AsyncMachine(model=self, **CONFIG)  # type: ignore
        self._machine.after_state_change = self.after_state_change.__name__  # type: ignore

        assert self.state
        assert callable(self.initialize)
        assert callable(self.run)
        assert callable(self.finish)
        assert callable(self.reset)
        assert callable(self.close)

    def __repr__(self) -> str:
        # e.g., "<StateMachine 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'

    async def after_state_change(self, event: EventData) -> None:
        if not (event.transition and event.transition.dest):
            # Internal transition
            return
        await self._callback.on_change_state(self.state)

    async def on_exit_created(self, _: EventData) -> None:
        await self._callback.start()

    async def on_enter_initialized(self, _: EventData) -> None:
        await self._callback.initialize_run()

    async def on_enter_running(self, _: EventData) -> None:
        await self._callback.start_run()

    async def on_close_while_running(self, _: EventData) -> None:
        await self._callback.wait_for_run_finish()

    async def wait(self) -> None:
        await self._callback.wait_for_run_finish()

    async def on_enter_finished(self, _: EventData) -> None:
        await self._callback.finish()

    async def on_exit_finished(self, _: EventData) -> None:
        await self._callback.on_exit_finished()

    async def on_enter_closed(self, _: EventData) -> None:
        await self._callback.close()

    async def on_reset(self, event: EventData) -> None:
        reset_options = event.kwargs.pop('reset_options')
        assert isinstance(reset_options, ResetOptions)
        assert not list(event.args)
        assert not event.kwargs
        await self._callback.reset(reset_options=reset_options)

    async def __aenter__(self) -> 'StateMachine':
        await self.initialize()
        return self

    async def __aexit__(self, *_: Any, **__: Any) -> None:
        await self.close()


class Imp:
    '''The interface to the finite state machine and the plugin hook.'''

    def __init__(self, context: Context) -> None:
        self._context = context
        self._hook = context.hook
        self._callback = Callback(context=context, machine=self)
        self._machine = StateMachine(callback=self._callback)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self._machine!r}>'

    @property
    def state(self) -> str:
        return self._machine.state

    async def initialize(self) -> bool:
        return await self._machine.initialize()

    async def run(self) -> bool:
        return await self._machine.run()

    async def finish(self) -> bool:
        return await self._machine.finish()

    async def reset(self, reset_options: ResetOptions) -> bool:
        return await self._machine.reset(reset_options=reset_options)

    async def close(self) -> bool:
        return await self._machine.close()

    async def send_command(self, command: Command) -> None:
        await self._hook.ahook.send_command(context=self._context, command=command)

    async def interrupt(self) -> None:
        await self._hook.ahook.interrupt(context=self._context)

    async def terminate(self) -> None:
        await self._hook.ahook.terminate(context=self._context)

    async def kill(self) -> None:
        await self._hook.ahook.kill(context=self._context)

    async def wait(self) -> None:
        await self._machine.wait()

    def format_exception(self) -> Optional[str]:
        return self._hook.hook.format_exception(context=self._context)

    def result(self) -> Any:
        return self._hook.hook.result(context=self._context)

    async def __aenter__(self) -> 'Imp':
        await self._machine.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self._machine.__aexit__(*args, **kwargs)
