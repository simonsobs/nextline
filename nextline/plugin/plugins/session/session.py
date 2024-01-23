from collections.abc import AsyncIterator
from logging import getLogger
from typing import Any, Optional

import apluggy
from tblib import pickling_support

from nextline.plugin.spec import Context, hookimpl
from nextline.spawned import Command, RunResult
from nextline.utils import ExitedProcess

from .spawn import run_session

pickling_support.install()


class RunSession:
    @hookimpl
    @apluggy.asynccontextmanager
    async def run(self, context: Context) -> AsyncIterator[None]:
        ahook = context.hook.ahook
        async with run_session(context) as running:
            await ahook.on_start_run(context=context)
            yield
            exited = await running
        if exited.raised:
            logger = getLogger(__name__)
            logger.exception(exited.raised)
        self._run_result = exited.returned or RunResult()
        await ahook.on_end_run(context=context, exited_process=exited)


class Signal:
    @hookimpl
    async def interrupt(self, context: Context) -> None:
        assert context.running_process
        context.running_process.interrupt()

    @hookimpl
    async def terminate(self, context: Context) -> None:
        assert context.running_process
        context.running_process.terminate()

    @hookimpl
    async def kill(self, context: Context) -> None:
        assert context.running_process
        context.running_process.kill()


class CommandSender:
    @hookimpl
    async def send_command(self, context: Context, command: Command) -> None:
        assert context.send_command
        context.send_command(command)


class Result:
    @hookimpl
    async def on_end_run(self, exited_process: ExitedProcess[RunResult]) -> None:
        self._run_result = exited_process.returned or RunResult()

    @hookimpl
    def exception(self) -> Optional[BaseException]:
        return self._run_result.exc

    @hookimpl
    def result(self) -> Any:
        return self._run_result.result()
