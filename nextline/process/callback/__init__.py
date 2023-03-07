from __future__ import annotations

from asyncio import Task
from contextlib import contextmanager
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, MutableMapping, Optional
from weakref import WeakKeyDictionary

from apluggy import PluginManager

from nextline.process.call import sys_trace
from nextline.process.types import CommandQueueMap
from nextline.types import RunNo, TraceNo

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

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

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


class Callback:
    def __init__(
        self,
        run_no: RunNo,
        registrar: RegistrarProxy,
        command_queue_map: CommandQueueMap,
    ):
        self._command_queue_map = command_queue_map
        trace_no_map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()

        self._hook = PluginManager(spec.PROJECT_NAME)
        self._hook.add_hookspecs(spec)

        self._logger = getLogger(__name__)

        stdout_registrar = StdoutRegistrar(run_no=run_no, registrar=registrar)
        add_module_to_trace = FilerByModule()
        trace_info_registrar = TraceInfoRegistrar(run_no=run_no, registrar=registrar)
        prompt_info_registrar = PromptInfoRegistrar(run_no=run_no, registrar=registrar)
        trace_numbers_registrar = TraceNumbersRegistrar(registrar=registrar)
        peek_stdout = PeekStdout(hook=self._hook)
        trace_mapper = TaskOrThreadToTraceMapper(
            trace_no_map=trace_no_map,
            hook=self._hook,
            command_queue_map=self._command_queue_map,
        )

        self._hook.register(stdout_registrar, name='stdout')
        self._hook.register(add_module_to_trace, name='add_module_to_trace')
        self._hook.register(trace_info_registrar, name='trace_info')
        self._hook.register(prompt_info_registrar, name='prompt_info')
        self._hook.register(trace_numbers_registrar, name='trace_numbers')
        self._hook.register(peek_stdout, name='peek_stdout')
        self._hook.register(trace_mapper, name='task_or_thread_to_trace_mapper')

        filter_lambda = FilterLambda()
        filter_by_module_name = FilterByModuleName(patterns=MODULES_TO_SKIP)

        self._hook.register(filter_lambda, name='filter_lambda')
        self._hook.register(filter_by_module_name, name='filter_by_module_name')

    def global_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        try:
            return self._hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
        except BaseException:
            self._logger.exception('')
            raise

    def start(self) -> None:
        self._hook.hook.start()

    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._hook.hook.close(
            exc_type=exc_type, exc_value=exc_value, traceback=traceback
        )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close(exc_type, exc_value, traceback)
