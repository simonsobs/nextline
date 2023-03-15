from contextlib import contextmanager
from logging import getLogger

from apluggy import PluginManager

from nextline.spawned.call import sys_trace
from nextline.spawned.types import CommandQueueMap, QueueOut
from nextline.types import RunNo

from . import plugins, spec

MODULES_TO_SKIP = {
    'multiprocessing.*',
    'threading',
    'queue',
    'importlib',
    'asyncio.*',
    'codec',
    'concurrent.futures.*',
    'selectors',
    'weakref',
    '_weakrefset',
    'socket',
    'logging',
    'os',
    'collections.*',
    'importlib.*',
    'pathlib',
    'typing',
    'posixpath',
    'fnmatch',
    '_pytest.*',
    'apluggy.*',
    'pluggy.*',
    sys_trace.__module__,  # skip the 1st line of the finally clause in sys_trace()
    contextmanager.__module__,  # to skip contextlib.__exit__() in sys_trace()
}


def build_hook(
    run_no: RunNo, command_queue_map: CommandQueueMap, queue_out: QueueOut
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

    logger = getLogger(__name__)
    plugin_names = (f'{n!r}' for n, p in hook.list_name_plugin() if p)
    msg = f'Loaded plugins: {",".join(plugin_names)}.'
    logger.info(msg)

    hook.hook.init(
        hook=hook,
        run_no=run_no,
        command_queue_map=command_queue_map,
        modules_to_skip=MODULES_TO_SKIP,
        queue_out=queue_out,
    )

    return hook
