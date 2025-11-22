from logging import getLogger

from apluggy import PluginManager

from nextline.spawned.types import QueueIn, QueueOut, RunArg

from . import plugins, skip, spec


def Hook(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> PluginManager:
    '''Return a plugin manager with the plugins registered.'''

    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    plugins.register(hook=hook, run_arg=run_arg)

    logger = getLogger(__name__)

    plugin_names = [n for n, p in hook.list_name_plugin() if p]
    logger.info(f'Pluggy project name: {hook.project_name!r}')
    logger.info(f'Loaded plugins: {plugin_names}')

    hook.hook.init(
        hook=hook,
        run_arg=run_arg,
        modules_to_skip=skip.MODULES_TO_SKIP,
        queue_in=queue_in,
        queue_out=queue_out,
    )

    return hook
