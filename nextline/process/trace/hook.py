from __future__ import annotations

from contextlib import contextmanager

from apluggy import PluginManager

from nextline.process.call import sys_trace
from nextline.process.types import CommandQueueMap, QueueRegistry
from nextline.types import RunNo

from . import spec
from .plugins import (
    FilerByModule,
    FilterByModuleName,
    FilterLambda,
    GlobalTraceFunc,
    LocalTraceFunc,
    PeekStdout,
    PromptInfoRegistrar,
    RegistrarProxy,
    StdoutRegistrar,
    TaskAndThreadKeeper,
    TaskOrThreadToTraceMapper,
    TraceCallHandler,
    TraceInfoRegistrar,
    TraceNumbersRegistrar,
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
) -> PluginManager:
    '''Return a plugin manager with the plugins registered.'''

    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    registrar = RegistrarProxy(queue=queue_registry)

    hook.register(StdoutRegistrar(), name='stdout')
    hook.register(FilerByModule(), name='add_module_to_trace')
    hook.register(TraceInfoRegistrar(), name='trace_info')
    hook.register(PromptInfoRegistrar(), name='prompt_info')
    hook.register(TraceNumbersRegistrar(), name='trace_numbers')
    hook.register(PeekStdout(), name='peek_stdout')

    hook.register(TraceCallHandler(), name='trace_call_handler')
    hook.register(LocalTraceFunc(), name='local_trace_func')

    hook.register(TaskOrThreadToTraceMapper(), name='task_or_thread_to_trace_mapper')
    hook.register(TaskAndThreadKeeper(), name='task_and_thread_keeper')

    hook.register(FilterLambda(), name='filter_lambda')
    hook.register(FilterByModuleName(), name='filter_by_module_name')

    hook.register(GlobalTraceFunc(), name='global_trace_func')

    hook.hook.init(
        hook=hook,
        run_no=run_no,
        registrar=registrar,
        command_queue_map=command_queue_map,
        modules_to_skip=MODULES_TO_SKIP,
    )

    return hook
