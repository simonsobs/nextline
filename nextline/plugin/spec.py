from pathlib import Path
from types import CodeType
from typing import Any, Callable, Optional, Union

import apluggy as pluggy
from apluggy import PluginManager

from nextline import spawned
from nextline.spawned import RunArg
from nextline.utils.pubsub.broker import PubSub

PROJECT_NAME = 'nextline_main'


hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def init(
    hook: PluginManager,
    registry: PubSub,
    run_no_start_from: int,
    statement: Union[str, Path, CodeType, Callable[[], Any]],
) -> None:
    pass


@hookspec
async def start() -> None:
    pass


@hookspec
async def close(exc_type=None, exc_value=None, traceback=None) -> None:
    pass


@hookspec
async def on_change_state(state_name: str) -> None:
    pass


@hookspec
async def on_change_script(script: str, filename: str) -> None:
    pass


@hookspec(firstresult=True)
def compose_run_arg() -> Optional[RunArg]:
    pass


@hookspec
async def reset(
    run_no_start_from: int,
    statement: Union[str, Path, CodeType, Callable[[], Any]],
) -> None:
    pass


@hookspec
async def on_initialize_run(run_arg: RunArg) -> None:
    pass


@hookspec
async def on_start_run() -> None:
    pass


@hookspec
async def on_end_run(run_result: spawned.RunResult) -> None:
    pass


@hookspec
async def on_start_trace(event: spawned.OnStartTrace) -> None:
    pass


@hookspec
async def on_end_trace(event: spawned.OnEndTrace) -> None:
    pass


@hookspec
async def on_start_trace_call(event: spawned.OnStartTraceCall) -> None:
    pass


@hookspec
async def on_end_trace_call(event: spawned.OnEndTraceCall) -> None:
    pass


@hookspec
async def on_start_cmdloop(event: spawned.OnStartCmdloop) -> None:
    pass


@hookspec
async def on_end_cmdloop(event: spawned.OnEndCmdloop) -> None:
    pass


@hookspec
async def on_start_prompt(event: spawned.OnStartPrompt) -> None:
    pass


@hookspec
async def on_end_prompt(event: spawned.OnEndPrompt) -> None:
    pass


@hookspec
async def on_write_stdout(event: spawned.OnWriteStdout) -> None:
    pass
