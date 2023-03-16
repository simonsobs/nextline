from apluggy import PluginManager

from . import plugins, spec


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    hook.register(plugins.StdoutRegistrar)
    hook.register(plugins.PromptInfoRegistrar)
    hook.register(plugins.TraceInfoRegistrar)
    hook.register(plugins.TraceNumbersRegistrar)
    hook.register(plugins.RunInfoRegistrar)
    hook.register(plugins.RunNoRegistrar)
    hook.register(plugins.StateNameRegistrar)
    hook.register(plugins.ScriptRegistrar)

    return hook
