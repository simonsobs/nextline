import threading
from asyncio import Task
from collections.abc import Generator, Iterable, Iterator
from functools import lru_cache, partial
from logging import getLogger
from threading import Thread
from typing import Optional

from apluggy import PluginManager, contextmanager

from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import TraceArgs
from nextline.utils import current_task_or_thread, match_any

from . import _script


class FilterByModuleName:
    '''Skip Python modules with names that match any of the patterns.'''

    @hookimpl
    def init(self, modules_to_skip: Iterable[str]) -> None:
        self._patterns = frozenset(modules_to_skip)

        # NOTE: Use lru_cache() as match_any() is slow
        self._match_any_ = lru_cache(partial(match_any, patterns=modules_to_skip))

    @hookimpl
    def filter(self, trace_args: TraceArgs) -> bool | None:
        frame = trace_args[0]
        module_name = frame.f_globals.get('__name__')
        matched = self._match_any_(module_name)
        return matched or None


class FilterLambda:
    '''Skip lambda functions.'''

    @hookimpl
    def filter(self, trace_args: TraceArgs) -> bool | None:
        frame = trace_args[0]
        func_name = frame.f_code.co_name
        return func_name == '<lambda>' or None


class FilterMainScript:
    '''Accept only the main script.'''

    @hookimpl
    def filter(self, trace_args: TraceArgs) -> bool | None:
        frame = trace_args[0]
        module_name = frame.f_globals.get('__name__')
        if _script.__name__ == module_name:
            return False
        return True


class FilerByModule:
    '''Accept the first module and modules ever in the cmdloop() context.'''

    def __init__(self) -> None:
        self._modules_to_trace = set[str]()
        self._first_module_added = False
        self._entering_thread: Optional[Thread] = None
        self._traced_tasks_and_threads = set[Task | Thread]()
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    @contextmanager
    def context(self) -> Iterator[None]:
        self._entering_thread = threading.current_thread()
        msg = f'{self.__class__.__name__}: entering thread {self._entering_thread}'
        self._logger.info(msg)
        yield

    @hookimpl(trylast=True)
    def filter(self, trace_args: TraceArgs) -> bool | None:
        # Accept the first module in the main thread.
        if not self._first_module_added:
            if self._entering_thread == threading.current_thread():
                self._add(trace_args)
                self._first_module_added = True

        # Accept tasks and threads once they are accepted.
        task_or_thread = current_task_or_thread()
        if task_or_thread in self._traced_tasks_and_threads:
            return None

        # Accept if the module was in the cmdloop() in other tasks or threads.
        if self._to_trace(trace_args):
            self._traced_tasks_and_threads.add(task_or_thread)
            return None

        # Reject else.
        return True

    @hookimpl
    @contextmanager
    def on_cmdloop(self) -> Generator[None, str, None]:
        trace_args = self._hook.hook.current_trace_args()
        self._add(trace_args)
        yield

    def _add(self, trace_args: TraceArgs) -> None:
        frame, _, _ = trace_args
        module_name = frame.f_globals.get('__name__')
        if module_name is None:
            return
        if module_name in self._modules_to_trace:
            return
        self._modules_to_trace.add(module_name)
        msg = f'{self.__class__.__name__}: added {module_name!r}'
        self._logger.info(msg)

    def _to_trace(self, trace_args: TraceArgs) -> bool:
        frame, _, _ = trace_args
        module_name = frame.f_globals.get('__name__')
        return match_any(module_name, self._modules_to_trace)
