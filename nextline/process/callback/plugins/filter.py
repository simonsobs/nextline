from __future__ import annotations

import threading
from asyncio import Task
from functools import lru_cache, partial
from logging import getLogger
from threading import Thread
from typing import Generator, Iterable, Optional, Set

from apluggy import contextmanager

from nextline.process.callback.spec import hookimpl
from nextline.process.callback.types import TraceArgs
from nextline.utils import current_task_or_thread, match_any


class FilterByModuleName:
    '''Skip Python modules with names that match any of the patterns.'''

    def __init__(self, patterns: Iterable[str]):
        self._patterns = frozenset(patterns)

        # NOTE: Use lru_cache() as match_any() is slow
        self._match_any_ = lru_cache(partial(match_any, patterns=patterns))

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


class FilerByModule:
    '''Let Python modules be traced in new threads and asyncio tasks.'''

    def __init__(self) -> None:
        self._modules_to_trace: Set[str] = set()
        self._first_module_added = False
        self._entering_thread: Optional[Thread] = None
        self._traced_tasks_and_threads: Set[Task | Thread] = set()
        self._logger = getLogger(__name__)

    @hookimpl(trylast=True)
    def filter(self, trace_args: TraceArgs) -> bool | None:
        if not self._first_module_added:
            if self._entering_thread == threading.current_thread():
                self._add(trace_args)
                self._first_module_added = True
        task_or_thread = current_task_or_thread()
        if task_or_thread in self._traced_tasks_and_threads:
            return None
        if self._to_trace(trace_args):
            self._traced_tasks_and_threads.add(task_or_thread)
            return None
        return True

    @hookimpl
    def start(self) -> None:
        self._entering_thread = threading.current_thread()
        msg = f'{self.__class__.__name__}: entering thread {self._entering_thread}'
        self._logger.info(msg)

    @hookimpl
    @contextmanager
    def cmdloop(self, trace_args: TraceArgs) -> Generator[None, str, None]:
        self._add(trace_args)
        yield

    def _add(self, trace_args: TraceArgs):
        frame, _, _ = trace_args
        module_name = frame.f_globals.get('__name__')
        if module_name is None:
            return
        msg = f'{self.__class__.__name__}: adding {module_name!r}'
        self._logger.info(msg)
        self._modules_to_trace.add(module_name)

    def _to_trace(self, trace_args: TraceArgs) -> bool:
        frame, _, _ = trace_args
        module_name = frame.f_globals.get('__name__')
        return match_any(module_name, self._modules_to_trace)
