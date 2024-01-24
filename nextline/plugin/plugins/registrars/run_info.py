import dataclasses
import datetime
from typing import Optional

from nextline.plugin.spec import Context, hookimpl
from nextline.types import RunInfo


class RunInfoRegistrar:
    def __init__(self) -> None:
        self._run_info: Optional[RunInfo] = None

    @hookimpl
    async def on_initialize_run(self, context: Context) -> None:
        assert context.run_arg
        if isinstance(context.run_arg.statement, str):
            script = context.run_arg.statement
        else:
            script = None
        self._run_info = RunInfo(
            run_no=context.run_arg.run_no, state='initialized', script=script
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
    async def on_end_run(self, context: Context) -> None:
        assert self._run_info is not None
        assert context.exited_process
        run_result = context.exited_process.returned
        assert run_result

        self._run_info = dataclasses.replace(
            self._run_info,
            state='finished',
            result=run_result.fmt_ret,
            exception=run_result.fmt_exc,
            ended_at=datetime.datetime.utcnow(),
        )
        await context.pubsub.publish('run_info', self._run_info)

        self._run_info = None
