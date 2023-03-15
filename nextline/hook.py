from apluggy import PluginManager

from . import plugins, spec


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    hook.register(plugins.StdoutRegistrar)
    hook.register(plugins.PromptInfoRegistrar)
    hook.register(plugins.TraceInfoRegistrar)
    hook.register(plugins.TraceNumbersRegistrar)

    return hook
