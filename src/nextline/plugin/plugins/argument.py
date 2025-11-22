from nextline.count import RunNoCounter
from nextline.plugin.spec import Context, hookimpl
from nextline.spawned import RunArg
from nextline.types import InitOptions, ResetOptions

SCRIPT_FILE_NAME = "<string>"


class RunArgComposer:
    @hookimpl
    def init(self, init_options: InitOptions) -> None:
        self._run_no_count = RunNoCounter(init_options.run_no_start_from)
        self._statement = init_options.statement
        self._filename = SCRIPT_FILE_NAME
        self._trace_threads = init_options.trace_threads
        self._trace_modules = init_options.trace_modules

    @hookimpl
    async def start(self, context: Context) -> None:
        await context.hook.ahook.on_change_script(
            context=context, script=self._statement, filename=self._filename
        )

    @hookimpl
    async def reset(self, context: Context, reset_options: ResetOptions) -> None:
        if (statement := reset_options.statement) is not None:
            self._statement = statement
            await context.hook.ahook.on_change_script(
                context=context, script=self._statement, filename=self._filename
            )
        if (run_no_start_from := reset_options.run_no_start_from) is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)
        if (trace_threads := reset_options.trace_threads) is not None:
            self._trace_threads = trace_threads
        if (trace_modules := reset_options.trace_modules) is not None:
            self._trace_modules = trace_modules

    @hookimpl
    def compose_run_arg(self) -> RunArg:
        run_arg = RunArg(
            run_no=self._run_no_count(),
            statement=self._statement,
            filename=self._filename,
            trace_threads=self._trace_threads,
            trace_modules=self._trace_modules,
        )
        return run_arg
