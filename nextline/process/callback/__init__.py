from __future__ import annotations

from asyncio import Task
from contextlib import contextmanager
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Dict, MutableMapping, Optional
from weakref import WeakKeyDictionary

from apluggy import PluginManager

from nextline.count import PromptNoCounter, TraceNoCounter
from nextline.process.call import sys_trace
from nextline.process.pdb.proxy import TraceCallCallback, instantiate_pdb
from nextline.process.types import CommandQueueMap
from nextline.types import RunNo, TraceNo
from nextline.utils import ThreadTaskIdComposer
from nextline.utils.func import current_task_or_thread

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
from .plugins.trace import CallbackForTrace

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
        self._trace_no_counter = TraceNoCounter(1)
        self._prompt_no_counter = PromptNoCounter(1)
        self._command_queue_map = command_queue_map
        self._trace_no_map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()

        self._local_trace_func_map: MutableMapping[
            Task | Thread, TraceFunc
        ] = WeakKeyDictionary()

        self._callback_for_trace_map: Dict[TraceNo, CallbackForTrace] = {}

        self._trace_id_factory = ThreadTaskIdComposer()

        self._hook = PluginManager(spec.PROJECT_NAME)
        self._hook.add_hookspecs(spec)

        self._logger = getLogger(__name__)

        stdout_registrar = StdoutRegistrar(run_no=run_no, registrar=registrar)
        add_module_to_trace = FilerByModule()
        trace_info_registrar = TraceInfoRegistrar(run_no=run_no, registrar=registrar)
        prompt_info_registrar = PromptInfoRegistrar(run_no=run_no, registrar=registrar)
        trace_numbers_registrar = TraceNumbersRegistrar(registrar=registrar)
        peek_stdout = PeekStdout(self)
        trace_mapper = TaskOrThreadToTraceMapper(self, self._trace_no_map)

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
        if self.filter(frame, event, arg):
            return None
        task_or_thread = current_task_or_thread()
        local_trace_func = self._local_trace_func_map.get(task_or_thread)
        if local_trace_func is None:
            callback_for_trace = self.task_or_thread_start()
            local_trace_func = self.create_local_trace_func(callback_for_trace)
            self._local_trace_func_map[task_or_thread] = local_trace_func
        return local_trace_func(frame, event, arg)

    def filter(self, frame: FrameType, event, arg) -> bool:
        accepted: bool | None = self._hook.hook.filter(trace_args=(frame, event, arg))
        return accepted or False

    def create_local_trace_func(self, callback_for_trace: CallbackForTrace):
        trace = instantiate_pdb(callback=callback_for_trace)

        trace = TraceCallCallback(trace=trace, callback=callback_for_trace)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace

    def task_or_thread_start(self) -> CallbackForTrace:
        trace_no = self._trace_no_counter()
        self._hook.hook.task_or_thread_start(trace_no=trace_no)
        return self._callback_for_trace_map[trace_no]

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        self._hook.hook.task_or_thread_end(task_or_thread=task_or_thread)

    def trace_start(self, trace_no: TraceNo):
        callback_for_trace = CallbackForTrace(
            trace_no=trace_no,
            hook=self._hook,
            command_queue_map=self._command_queue_map,
            trace_id_factory=self._trace_id_factory,
            prompt_no_counter=self._prompt_no_counter,
        )
        self._callback_for_trace_map[trace_no] = callback_for_trace
        callback_for_trace.trace_start()

    def trace_end(self, trace_no: TraceNo):
        self._callback_for_trace_map[trace_no].trace_end()
        del self._callback_for_trace_map[trace_no]

    def stdout(self, task_or_thread: Task | Thread, line: str):
        trace_no = self._trace_no_map[task_or_thread]
        self._hook.hook.stdout(trace_no=trace_no, line=line)

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
