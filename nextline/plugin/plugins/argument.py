from apluggy import PluginManager

from nextline.count import RunNoCounter
from nextline.plugin.spec import hookimpl
from nextline.spawned import RunArg
from nextline.types import InitOptions, ResetOptions
from nextline.utils.pubsub.broker import PubSub

SCRIPT_FILE_NAME = "<string>"


class RunArgComposer:
    @hookimpl
    def init(
        self,
        hook: PluginManager,
        registry: PubSub,
        init_options: InitOptions,
    ) -> None:
        self._hook = hook
        self._registry = registry
        self._run_no_count = RunNoCounter(init_options.run_no_start_from)
        self._statement = init_options.statement
        self._filename = SCRIPT_FILE_NAME
        self._trace_threads = init_options.trace_threads

    @hookimpl
    async def start(self) -> None:
        await self._hook.ahook.on_change_script(
            script=self._statement,
            filename=self._filename,
        )

    @hookimpl
    async def reset(
        self,
        reset_options: ResetOptions,
    ) -> None:
        if (statement := reset_options.statement) is not None:
            self._statement = statement
            await self._hook.ahook.on_change_script(
                script=self._statement,
                filename=self._filename,
            )
        if (run_no_start_from := reset_options.run_no_start_from) is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)
        if (trace_threads := reset_options.trace_threads) is not None:
            self._trace_threads = trace_threads

    @hookimpl
    def compose_run_arg(self) -> RunArg:
        run_arg = RunArg(
            run_no=self._run_no_count(),
            statement=self._statement,
            filename=self._filename,
            trace_threads=self._trace_threads,
        )
        return run_arg
