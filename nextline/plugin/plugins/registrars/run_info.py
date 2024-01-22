import dataclasses
import datetime
from typing import Optional

from nextline import spawned
from nextline.plugin.spec import Context, hookimpl
from nextline.types import RunInfo
from nextline.utils import ExitedProcess


class RunInfoRegistrar:
    def __init__(self) -> None:
        self._script: Optional[str] = None
        self._run_info: Optional[RunInfo] = None

    @hookimpl
    async def on_change_script(self, script: str) -> None:
        self._script = script

    @hookimpl
    async def on_initialize_run(self, context: Context) -> None:
        assert context.run_arg
        self._run_info = RunInfo(
            run_no=context.run_arg.run_no, state='initialized', script=self._script
        )
        await context.pubsub.publish('run_info', self._run_info)

    @hookimpl
    async def on_start_run(self, context: Context) -> None:
        assert self._run_info is not None
        self._run_info = dataclasses.replace(
            self._run_info,
            state='running',
            started_at=datetime.datetime.utcnow(),
        )
        await context.pubsub.publish('run_info', self._run_info)

    @hookimpl
    async def on_end_run(
        self, context: Context, exited_process: ExitedProcess[spawned.RunResult]
    ) -> None:
        assert self._run_info is not None
        run_result = exited_process.returned or spawned.RunResult()

        self._run_info = dataclasses.replace(
            self._run_info,
            state='finished',
            result=run_result.fmt_ret,
            exception=run_result.fmt_exc,
            ended_at=datetime.datetime.utcnow(),
        )
        await context.pubsub.publish('run_info', self._run_info)

        self._run_info = None
