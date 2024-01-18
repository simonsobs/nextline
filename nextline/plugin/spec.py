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


@hookspec
def init(
    nextline: 'Nextline',
    hook: apluggy.PluginManager,
    registry: PubSub,
    init_options: InitOptions,
) -> None:
    pass


@hookspec
async def start() -> None:
    pass


@hookspec
async def close(exc_type=None, exc_value=None, traceback=None) -> None:  # type: ignore
    pass


@hookspec
async def reset(reset_options: ResetOptions) -> None:
    pass


@hookspec
async def on_change_state(state_name: str) -> None:
    pass


@hookspec
async def on_change_script(script: str, filename: str) -> None:
    pass


@hookspec(firstresult=True)
def compose_run_arg() -> Optional[spawned.RunArg]:
    pass


@hookspec
async def on_initialize_run(run_arg: spawned.RunArg) -> None:
    pass


@hookspec
@apluggy.asynccontextmanager
async def run():  # type: ignore
    yield


@hookspec
async def on_start_run(
    running_process: RunningProcess[spawned.RunResult],
    send_command: Callable[[spawned.Command], None],
) -> None:
    pass


@hookspec
async def interrupt() -> None:
    pass


@hookspec
async def terminate() -> None:
    pass


@hookspec
async def kill() -> None:
    pass


@hookspec
async def send_command(command: spawned.Command) -> None:
    pass


@hookspec
async def on_end_run(exited_process: ExitedProcess[spawned.RunResult]) -> None:
    pass


@hookspec(firstresult=True)
def exception() -> Optional[BaseException]:
    pass


@hookspec(firstresult=True)
def result() -> Any:
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
