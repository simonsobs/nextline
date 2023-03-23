__all__ = ['register']

from apluggy import PluginManager

from .argument import RunArgComposer
from .registrars import (
    PromptInfoRegistrar,
    PromptNoticeRegistrar,
    RunInfoRegistrar,
    RunNoRegistrar,
    ScriptRegistrar,
    StateNameRegistrar,
    StdoutRegistrar,
    TraceInfoRegistrar,
    TraceNumbersRegistrar,
)
from .run_session import RunSession


def register(hook: PluginManager) -> None:
    hook.register(StdoutRegistrar)
    hook.register(PromptNoticeRegistrar)
    hook.register(PromptInfoRegistrar)
    hook.register(TraceInfoRegistrar)
    hook.register(TraceNumbersRegistrar)
    hook.register(RunInfoRegistrar)
    hook.register(RunNoRegistrar)
    hook.register(StateNameRegistrar)
    hook.register(ScriptRegistrar)
    hook.register(RunArgComposer)
    hook.register(RunSession)
