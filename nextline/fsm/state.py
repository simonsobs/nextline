import asyncio
from typing import Any, Optional

from transitions import EventData

from nextline.plugin import build_hook
from nextline.spawned import Command, Statement
from nextline.utils.pubsub.broker import PubSub

from .factory import build_state_machine


class Machine:
    '''The finite state machine of the nextline states.'''

    def __init__(self, run_no_start_from: int, statement: Statement):
        self.registry = PubSub[Any, Any]()
        self._hook = build_hook()
        self._hook.hook.init(
            hook=self._hook,
            registry=self.registry,
            run_no_start_from=run_no_start_from,
            statement=statement,
        )

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
        await self.registry.close()
        await self._hook.ahook.close()

    async def on_reset(self, event: EventData) -> None:
        # TODO: Check the arguments
        await self._hook.ahook.reset(*event.args, **event.kwargs)

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()
