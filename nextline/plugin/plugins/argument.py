from typing import Optional

from apluggy import PluginManager

from nextline.count import RunNoCounter
from nextline.plugin.spec import hookimpl
from nextline.spawned import RunArg, Statement
from nextline.utils.pubsub.broker import PubSub

SCRIPT_FILE_NAME = "<string>"


class RunArgComposer:
    @hookimpl
    def init(
        self,
        hook: PluginManager,
        registry: PubSub,
        run_no_start_from: int,
        statement: Statement,
    ) -> None:
        self._hook = hook
        self._registry = registry
        self._run_no_count = RunNoCounter(run_no_start_from)
        self._statement = statement
        self._filename = SCRIPT_FILE_NAME

    @hookimpl
    async def start(self) -> None:
        await self._hook.ahook.on_change_script(
            script=self._statement,
            filename=self._filename,
        )

    @hookimpl
    async def reset(
        self, run_no_start_from: Optional[int], statement: Optional[Statement]
    ) -> None:
        if statement is not None:
            self._statement = statement
            await self._hook.ahook.on_change_script(
                script=self._statement,
                filename=self._filename,
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)

    @hookimpl
    def compose_run_arg(self) -> RunArg:
        run_arg = RunArg(
            run_no=self._run_no_count(),
            statement=self._statement,
            filename=self._filename,
        )
        return run_arg
