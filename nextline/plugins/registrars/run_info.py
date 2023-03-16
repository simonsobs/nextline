import dataclasses
import datetime
from typing import Optional

from apluggy import PluginManager

from nextline import spawned
from nextline.spec import hookimpl
from nextline.types import RunInfo, RunNo
from nextline.utils.pubsub.broker import PubSub


class RunInfoRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._script: Optional[str] = None
        self._run_info: Optional[RunInfo] = None

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_change_script(self, script: str) -> None:
        self._script = script

    @hookimpl
    async def on_initialize_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._run_info = RunInfo(
            run_no=run_no, state='initialized', script=self._script
        )
        await self._registry.publish('run_info', self._run_info)

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        assert self._run_info is not None
        self._run_info = dataclasses.replace(
            self._run_info,
            state='running',
            started_at=datetime.datetime.utcnow(),
        )
        await self._registry.publish('run_info', self._run_info)

    @hookimpl
    async def on_end_run(self, run_no: RunNo, run_result: spawned.RunResult) -> None:
        assert self._run_no == run_no
        assert self._run_info is not None

        self._run_info = dataclasses.replace(
            self._run_info,
            state='finished',
            result=run_result.fmt_ret,
            exception=run_result.fmt_exc,
            ended_at=datetime.datetime.utcnow(),
        )
        await self._registry.publish('run_info', self._run_info)

        self._run_info = None
        self._run_no = None
