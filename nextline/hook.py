from apluggy import PluginManager

from . import spec
from .plugins import PromptInfoRegistrar, TraceInfoRegistrar, TraceNumbersRegistrar


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    hook.register(PromptInfoRegistrar)
    hook.register(TraceInfoRegistrar)
    hook.register(TraceNumbersRegistrar)

    return hook
