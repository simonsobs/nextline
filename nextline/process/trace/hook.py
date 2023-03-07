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
    PeekStdout,
    PromptInfoRegistrar,
    RegistrarProxy,
    StdoutRegistrar,
    TaskOrThreadToTraceMapper,
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

    hook = PluginManager(spec.PROJECT_NAME)
    hook.add_hookspecs(spec)

    registrar = RegistrarProxy(queue=queue_registry)

    stdout_registrar = StdoutRegistrar(run_no=run_no, registrar=registrar)
    add_module_to_trace = FilerByModule()
    trace_info_registrar = TraceInfoRegistrar(run_no=run_no, registrar=registrar)
    prompt_info_registrar = PromptInfoRegistrar(run_no=run_no, registrar=registrar)
    trace_numbers_registrar = TraceNumbersRegistrar(registrar=registrar)
    peek_stdout = PeekStdout(hook=hook)
    trace_mapper = TaskOrThreadToTraceMapper(
        hook=hook, command_queue_map=command_queue_map
    )

    hook.register(stdout_registrar, name='stdout')
    hook.register(add_module_to_trace, name='add_module_to_trace')
    hook.register(trace_info_registrar, name='trace_info')
    hook.register(prompt_info_registrar, name='prompt_info')
    hook.register(trace_numbers_registrar, name='trace_numbers')
    hook.register(peek_stdout, name='peek_stdout')
    hook.register(trace_mapper, name='task_or_thread_to_trace_mapper')

    filter_lambda = FilterLambda()
    filter_by_module_name = FilterByModuleName(patterns=MODULES_TO_SKIP)

    hook.register(filter_lambda, name='filter_lambda')
    hook.register(filter_by_module_name, name='filter_by_module_name')

    return hook
