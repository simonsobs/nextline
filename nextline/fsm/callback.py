import asyncio
from logging import getLogger
from typing import TYPE_CHECKING

from nextline.plugin import Context
from nextline.types import ResetOptions

if TYPE_CHECKING:
    from .machine import StateMachine


class Callback:
    def __init__(self, context: Context) -> None:
        self._context = context
        self._hook = context.hook
        self._machine: 'StateMachine'  # To be set by StateMachine
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
        self._task_run = asyncio.create_task(self._run(started=started))
        await started.wait()

    async def _run(self, started: asyncio.Event) -> None:
        try:
            async with self._hook.awith.run(context=self._context):
                started.set()
        except BaseException:
            self._logger.exception('')
            raise
        finally:
            started.set()  # Ensure to unblock the await
            await self._finish()

    async def _finish(self) -> None:
        self._context.run_arg = None
        try:
            await self._machine.finish()
        except BaseException:
            self._logger.exception('')
            raise
        finally:
            self._run_finished.set()

    async def finish(self) -> None:
        # The state is already `finished`. The `on_change_state()` method will
        # be called after this method completes.
        await self._hook.ahook.on_finished(context=self._context)

    async def wait_for_run_finish(self) -> None:
        await self._run_finished.wait()

    async def on_exit_finished(self) -> None:
        # This task is awaited here rather than in `finish()` because
        # the task ends after `finish()` completes.
        await self._task_run

    async def close(self) -> None:
        await self._hook.ahook.close(context=self._context)

    async def reset(self, reset_options: ResetOptions) -> None:
        await self._hook.ahook.reset(context=self._context, reset_options=reset_options)
