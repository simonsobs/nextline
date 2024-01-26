from logging import getLogger

from apluggy import PluginManager

from . import plugins, spec


def build_hook() -> PluginManager:
    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)
    plugins.register(hook)
    return hook


def log_loaded_plugins(hook: PluginManager) -> None:
    logger = getLogger(__name__)
    plugin_names = [n for n, p in hook.list_name_plugin() if p]
    logger.info(f'Pluggy project name: {hook.project_name!r}')
    logger.info(f'Loaded plugins: {plugin_names}')
