import asyncio
from pathlib import Path
from types import CodeType
from typing import Any, Callable, Optional, Union

from transitions import EventData

from nextline.context import Context
from nextline.spawned import Command, RunResult

from .factory import build_state_machine


class Machine:
    '''The finite state machine of the nextline states.'''

    def __init__(
        self,
        run_no_start_from: int,
        statement: Union[str, Path, CodeType, Callable[[], Any]],
    ):
        self._context = Context(
            run_no_start_from=run_no_start_from,
            statement=statement,
        )
        self.registry = self._context.registry

        self._machine = build_state_machine(model=self)
        self._machine.after_state_change = self.after_state_change.__name__  # type: ignore

        assert self.state  # type: ignore

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'

    async def after_state_change(self, event: EventData) -> None:
        if not (event.transition and event.transition.dest):
            # internal transition
            return
        await self._context.state_change(self.state)  # type: ignore

    async def on_exit_created(self, _: EventData) -> None:
        await self._context.start()

    async def on_enter_initialized(self, _: EventData) -> None:
        await self._context.initialize()

    async def on_enter_running(self, _: EventData) -> None:
        self.run_finished = asyncio.Event()
        run_started = asyncio.Event()

        async def run() -> None:
            async with (c := self._context.run()) as (running, send_command):
                self._running = running
                self._send_command = send_command
                run_started.set()
                exited = await running
                self._exited = exited
                self._run_result = exited.returned or RunResult(ret=None, exc=None)
                await c.gen.asend(exited)
            await self.finish()  # type: ignore
            self.run_finished.set()

        self._task = asyncio.create_task(run())
        await run_started.wait()

    async def on_send_command(self, event: EventData) -> None:
        command, *_ = event.args
        assert isinstance(command, Command)
        self._send_command(command)

    async def on_interrupt(self, _: EventData) -> None:
        self._running.interrupt()

    async def on_terminate(self, _: EventData) -> None:
        self._running.terminate()

    async def on_kill(self, _: EventData) -> None:
        self._running.kill()

    async def on_close_while_running(self, _: EventData) -> None:
        await self.run_finished.wait()

    async def wait(self) -> None:
        await self.run_finished.wait()

    async def on_exit_finished(self, _: EventData) -> None:
        await self._task

    def exception(self) -> Optional[BaseException]:
        return self._run_result.exc

    def result(self) -> Any:
        return self._run_result.result()

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
