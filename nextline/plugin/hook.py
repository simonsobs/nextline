from apluggy import PluginManager

from . import plugins, spec


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)
    plugins.register(hook)
    return hook
