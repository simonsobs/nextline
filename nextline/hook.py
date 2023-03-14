from apluggy import PluginManager

from . import spec


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)
    hook.hook.init(hook=hook)
    return hook
