from collections.abc import Callable, Coroutine
from typing import Any, Protocol, TypeAlias

from transitions import EventData
from transitions.extensions.asyncio import AsyncMachine

from nextline.types import ResetOptions

from .callback import Callback
from .config import CONFIG

TriggerNoArg: TypeAlias = Callable[[], Coroutine[None, None, bool]]


class Reset(Protocol):
    def __call__(self, *, reset_options: ResetOptions) -> Coroutine[None, None, bool]:
        ...


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
        machine = AsyncMachine(model=self, **CONFIG)  # type: ignore
        machine.after_state_change = self.after_state_change.__name__  # type: ignore

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
