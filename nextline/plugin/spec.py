import dataclasses
from typing import TYPE_CHECKING, Any, Callable, Optional

import apluggy

from nextline import spawned
from nextline.types import InitOptions, ResetOptions
from nextline.utils import ExitedProcess, RunningProcess
from nextline.utils.pubsub.broker import PubSub

if TYPE_CHECKING:
    from nextline import Nextline

PROJECT_NAME = 'nextline_main'


hookspec = apluggy.HookspecMarker(PROJECT_NAME)
hookimpl = apluggy.HookimplMarker(PROJECT_NAME)


@dataclasses.dataclass
class Context:
    nextline: 'Nextline'
    hook: apluggy.PluginManager
    pubsub: PubSub


@hookspec
def init(context: Context, init_options: InitOptions) -> None:
    pass


@hookspec
async def start(context: Context) -> None:
    pass


@hookspec
async def close(
    context: Context, exc_type=None, exc_value=None, traceback=None
) -> None:
    pass


@hookspec
async def reset(context: Context, reset_options: ResetOptions) -> None:
    pass


@hookspec
async def on_change_state(context: Context, state_name: str) -> None:
    pass


@hookspec
async def on_change_script(context: Context, script: str, filename: str) -> None:
    pass


@hookspec(firstresult=True)
def compose_run_arg(context: Context) -> Optional[spawned.RunArg]:
    pass


@hookspec
async def on_initialize_run(context: Context, run_arg: spawned.RunArg) -> None:
    pass


@hookspec
@apluggy.asynccontextmanager
async def run(context: Context):  # type: ignore
    yield


@hookspec
async def on_start_run(
    context: Context,
    running_process: RunningProcess[spawned.RunResult],
    send_command: Callable[[spawned.Command], None],
) -> None:
    pass


@hookspec
async def interrupt(context: Context) -> None:
    pass


@hookspec
async def terminate(context: Context) -> None:
    pass


@hookspec
async def kill(context: Context) -> None:
    pass


@hookspec
async def send_command(context: Context, command: spawned.Command) -> None:
    pass


@hookspec
async def on_end_run(
    context: Context, exited_process: ExitedProcess[spawned.RunResult]
) -> None:
    pass


@hookspec(firstresult=True)
def exception(context: Context) -> Optional[BaseException]:
    pass


@hookspec(firstresult=True)
def result(context: Context) -> Any:
    pass


@hookspec
async def on_start_trace(context: Context, event: spawned.OnStartTrace) -> None:
    pass


@hookspec
async def on_end_trace(context: Context, event: spawned.OnEndTrace) -> None:
    pass


@hookspec
async def on_start_trace_call(
    context: Context, event: spawned.OnStartTraceCall
) -> None:
    pass


@hookspec
async def on_end_trace_call(context: Context, event: spawned.OnEndTraceCall) -> None:
    pass


@hookspec
async def on_start_cmdloop(context: Context, event: spawned.OnStartCmdloop) -> None:
    pass


@hookspec
async def on_end_cmdloop(context: Context, event: spawned.OnEndCmdloop) -> None:
    pass


@hookspec
async def on_start_prompt(context: Context, event: spawned.OnStartPrompt) -> None:
    pass


@hookspec
async def on_end_prompt(context: Context, event: spawned.OnEndPrompt) -> None:
    pass


@hookspec
async def on_write_stdout(context: Context, event: spawned.OnWriteStdout) -> None:
    pass
