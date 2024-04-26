import dataclasses
from typing import TYPE_CHECKING, Any, Callable, Optional

import apluggy

from nextline import events, spawned
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
    run_arg: spawned.RunArg | None = None
    send_command: Callable[[spawned.Command], None] | None = None
    running_process: RunningProcess[spawned.RunResult] | None = None
    exited_process: ExitedProcess[spawned.RunResult] | None = None


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
async def on_initialize_run(context: Context) -> None:
    pass


@hookspec
@apluggy.asynccontextmanager
async def run(context: Context):  # type: ignore
    yield


@hookspec
async def on_event_in_process(context: Context, event: events.Event) -> None:
    pass


@hookspec
async def on_start_run(context: Context) -> None:
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
async def on_end_run(context: Context) -> None:
    '''The run is about to finish. The state is still 'running'.'''
    pass


@hookspec
async def on_finished(context: Context) -> None:
    '''The run has finished. The state is 'finished'.'''
    pass


@hookspec(firstresult=True)
def format_exception(context: Context) -> Optional[str]:
    pass


@hookspec(firstresult=True)
def result(context: Context) -> Any:
    pass


@hookspec
async def on_start_trace(context: Context, event: events.OnStartTrace) -> None:
    pass


@hookspec
async def on_end_trace(context: Context, event: events.OnEndTrace) -> None:
    pass


@hookspec
async def on_start_trace_call(
    context: Context, event: events.OnStartTraceCall
) -> None:
    pass


@hookspec
async def on_end_trace_call(context: Context, event: events.OnEndTraceCall) -> None:
    pass


@hookspec
async def on_start_cmdloop(context: Context, event: events.OnStartCmdloop) -> None:
    pass


@hookspec
async def on_end_cmdloop(context: Context, event: events.OnEndCmdloop) -> None:
    pass


@hookspec
async def on_start_prompt(context: Context, event: events.OnStartPrompt) -> None:
    pass


@hookspec
async def on_end_prompt(context: Context, event: events.OnEndPrompt) -> None:
    pass


@hookspec
async def on_write_stdout(context: Context, event: events.OnWriteStdout) -> None:
    pass
