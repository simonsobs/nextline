from logging import getLogger

from apluggy import PluginManager

from nextline.spawned.types import QueueIn, QueueOut, RunArg

from . import plugins, skip, spec


def build_hook(
    run_arg: RunArg,
    queue_in: QueueIn,
    queue_out: QueueOut,
) -> PluginManager:
    '''Return a plugin manager with the plugins registered.'''

    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    hook.register(plugins.Repeater)
    hook.register(plugins.PeekStdout)
    hook.register(plugins.Prompt)
    hook.register(plugins.PdbInstanceFactory)
    hook.register(plugins.TraceCallHandler)
    hook.register(plugins.LocalTraceFunc)
    hook.register(plugins.TaskOrThreadToTraceMapper)
    hook.register(plugins.TaskAndThreadKeeper)
    hook.register(plugins.FilerByModule)
    hook.register(plugins.FilterLambda)
    hook.register(plugins.FilterByModuleName)
    hook.register(plugins.GlobalTraceFunc)
    hook.register(plugins.TraceFuncCreator)
    hook.register(plugins.CallableComposer)

    logger = getLogger(__name__)
    plugin_names = (f'{n!r}' for n, p in hook.list_name_plugin() if p)
    msg = f'Loaded plugins: {",".join(plugin_names)}.'
    logger.info(msg)

    hook.hook.init(
        hook=hook,
        run_arg=run_arg,
        modules_to_skip=skip.MODULES_TO_SKIP,
        queue_in=queue_in,
        queue_out=queue_out,
    )

    return hook
