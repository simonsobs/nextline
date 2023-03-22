from logging import getLogger

from apluggy import PluginManager

from nextline.spawned.types import QueueIn, QueueOut, RunArg

from . import plugins, skip, spec


def Hook(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> PluginManager:
    '''Return a plugin manager with the plugins registered.'''

    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    plugins.register(hook)

    logger = getLogger(__name__)
    plugin_names = (f'{n!r}' for n, p in hook.list_name_plugin() if p)
    msg = f'Loaded plugins ({spec.PROJECT_NAME!r}): {",".join(plugin_names)}.'
    logger.info(msg)

    hook.hook.init(
        hook=hook,
        run_arg=run_arg,
        modules_to_skip=skip.MODULES_TO_SKIP,
        queue_in=queue_in,
        queue_out=queue_out,
    )

    return hook
