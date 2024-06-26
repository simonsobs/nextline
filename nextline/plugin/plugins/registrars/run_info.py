import dataclasses
from datetime import timezone
from typing import Optional

from nextline.events import OnEndRun, OnStartRun
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
    async def on_start_run(self, context: Context, event: OnStartRun) -> None:
        assert self._run_info is not None
        assert event.started_at.tzinfo is timezone.utc
        started_at = event.started_at.replace(tzinfo=None)
        self._run_info = dataclasses.replace(
            self._run_info, state='running', started_at=started_at
        )
        await context.pubsub.publish('run_info', self._run_info)

    @hookimpl
    async def on_end_run(self, context: Context, event: OnEndRun) -> None:
        assert self._run_info is not None
        assert event.ended_at.tzinfo is timezone.utc
        ended_at = event.ended_at.replace(tzinfo=None)

        self._run_info = dataclasses.replace(
            self._run_info,
            state='finished',
            result=event.returned,
            exception=event.raised,
            ended_at=ended_at,
        )
        await context.pubsub.publish('run_info', self._run_info)
        self._run_info = None
