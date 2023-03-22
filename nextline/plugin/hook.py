from logging import getLogger

from apluggy import PluginManager

from . import plugins, spec


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    plugins.register(hook)

    logger = getLogger(__name__)
    plugin_names = (f'{n!r}' for n, p in hook.list_name_plugin() if p)
    msg = f'Loaded plugins ({spec.PROJECT_NAME!r}): {",".join(plugin_names)}.'
    logger.info(msg)

    return hook
