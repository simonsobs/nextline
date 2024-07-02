from typing import Any, Optional

from nextline.plugin import Context
from nextline.spawned import Command
from nextline.types import ResetOptions

from .fsm import Callback, StateMachine


class Imp:
    '''The interface to the finite state machine and the plugin hook.'''

    def __init__(self, context: Context) -> None:
        self._context = context
        self._hook = context.hook
        self._callback = Callback(context=context)
        self._machine = StateMachine(callback=self._callback)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self._machine!r}>'

    @property
    def state(self) -> str:
        return self._machine.state

    async def run(self) -> bool:
        return await self._machine.run()

    async def wait(self) -> None:
        await self._callback.wait_for_run_finish()

    async def reset(self, reset_options: ResetOptions) -> bool:
        return await self._machine.reset(reset_options=reset_options)

    async def send_command(self, command: Command) -> None:
        await self._hook.ahook.send_command(context=self._context, command=command)

    async def interrupt(self) -> None:
        await self._hook.ahook.interrupt(context=self._context)

    async def terminate(self) -> None:
        await self._hook.ahook.terminate(context=self._context)

    async def kill(self) -> None:
        await self._hook.ahook.kill(context=self._context)

    def format_exception(self) -> Optional[str]:
        return self._hook.hook.format_exception(context=self._context)

    def result(self) -> Any:
        return self._hook.hook.result(context=self._context)

    async def aopen(self) -> None:
        await self._machine.aopen()

    async def aclose(self) -> None:
        await self._machine.aclose()

    async def __aenter__(self) -> 'Imp':
        await self.aopen()
        return self

    async def __aexit__(self, *_: Any, **__: Any) -> None:
        await self.aclose()
