import apluggy as pluggy
from apluggy import PluginManager

from nextline.spawned import (
    OnEndCmdloop,
    OnEndPrompt,
    OnEndTrace,
    OnEndTraceCall,
    OnStartCmdloop,
    OnStartPrompt,
    OnStartTrace,
    OnStartTraceCall,
    OnWriteStdout,
)
from nextline.types import RunNo

PROJECT_NAME = 'nextline_callback'


hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def init(hook: PluginManager) -> None:
    pass


@hookspec
async def start() -> None:
    pass


@hookspec
async def close(exc_type=None, exc_value=None, traceback=None) -> None:
    pass


@hookspec
async def on_start_run(run_no: RunNo) -> None:
    pass


@hookspec
async def on_end_run(run_no: RunNo) -> None:
    pass


@hookspec
async def on_start_trace(event: OnStartTrace) -> None:
    pass


@hookspec
async def on_end_trace(event: OnEndTrace) -> None:
    pass


@hookspec
async def on_start_trace_call(event: OnStartTraceCall) -> None:
    pass


@hookspec
async def on_end_trace_call(event: OnEndTraceCall) -> None:
    pass


@hookspec
async def on_start_cmdloop(event: OnStartCmdloop) -> None:
    pass


@hookspec
async def on_end_cmdloop(event: OnEndCmdloop) -> None:
    pass


@hookspec
async def on_start_prompt(event: OnStartPrompt) -> None:
    pass


@hookspec
async def on_end_prompt(event: OnEndPrompt) -> None:
    pass


@hookspec
async def on_write_stdout(event: OnWriteStdout) -> None:
    pass
