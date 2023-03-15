from __future__ import annotations

from contextlib import contextmanager
from logging import getLogger

from apluggy import PluginManager

from nextline.spawned.call import sys_trace
from nextline.spawned.types import CommandQueueMap, QueueOut, QueueRegistry
from nextline.types import RunNo

from . import spec
from .plugins import (
    FilerByModule,
    FilterByModuleName,
    FilterLambda,
    GlobalTraceFunc,
    LocalTraceFunc,
    PdbInstanceFactory,
    PeekStdout,
    Prompt,
    PromptInfoRegistrar,
    RegistrarProxy,
    Repeater,
    StdoutRegistrar,
    TaskAndThreadKeeper,
    TaskOrThreadToTraceMapper,
    TraceCallHandler,
)

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
    run_no: RunNo,
    queue_registry: QueueRegistry,
    command_queue_map: CommandQueueMap,
    queue_out: QueueOut,
) -> PluginManager:
    '''Return a plugin manager with the plugins registered.'''

    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    registrar = RegistrarProxy(queue=queue_registry)

    hook.register(StdoutRegistrar)
    hook.register(PromptInfoRegistrar)

    hook.register(Repeater)

    hook.register(PeekStdout)

    hook.register(Prompt)
    hook.register(PdbInstanceFactory)

    hook.register(TraceCallHandler)
    hook.register(LocalTraceFunc)

    hook.register(TaskOrThreadToTraceMapper)
    hook.register(TaskAndThreadKeeper)

    hook.register(FilerByModule)
    hook.register(FilterLambda)
    hook.register(FilterByModuleName)

    hook.register(GlobalTraceFunc)

    logger = getLogger(__name__)
    plugin_names = (f'{n!r}' for n, p in hook.list_name_plugin() if p)
    msg = f'Loaded plugins: {",".join(plugin_names)}.'
    logger.info(msg)

    hook.hook.init(
        hook=hook,
        run_no=run_no,
        registrar=registrar,
        command_queue_map=command_queue_map,
        modules_to_skip=MODULES_TO_SKIP,
        queue_out=queue_out,
    )

    return hook
