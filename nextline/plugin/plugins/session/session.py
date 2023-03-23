from logging import getLogger
from typing import Any, AsyncIterator, Optional

import apluggy
from tblib import pickling_support

from nextline.plugin.spec import hookimpl
from nextline.spawned import Command, RunArg, RunResult

from .spawn import run_with_resource

pickling_support.install()


class RunSession:
    @hookimpl
    def init(self, hook: apluggy.PluginManager) -> None:
        self._hook = hook

    @hookimpl
    async def on_initialize_run(self, run_arg: RunArg) -> None:
        self._run_arg = run_arg

    @hookimpl
    @apluggy.asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        con = run_with_resource(self._hook, self._run_arg)
        async with con as (running, send_command):
            await self._hook.ahook.on_start_run()
            self._running = running
            self._send_command = send_command
            yield
            exited = await running
        if exited.raised:
            logger = getLogger(__name__)
            logger.exception(exited.raised)
        self._run_result = exited.returned or RunResult(ret=None, exc=None)
        await self._hook.ahook.on_end_run(run_result=self._run_result)

    @hookimpl
    async def send_command(self, command: Command) -> None:
        self._send_command(command)

    @hookimpl
    async def interrupt(self) -> None:
        self._running.interrupt()

    @hookimpl
    async def terminate(self) -> None:
        self._running.terminate()

    @hookimpl
    async def kill(self) -> None:
        self._running.kill()

    @hookimpl
    def exception(self) -> Optional[BaseException]:
        return self._run_result.exc

    @hookimpl
    def result(self) -> Any:
        return self._run_result.result()
