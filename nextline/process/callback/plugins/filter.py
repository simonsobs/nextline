from __future__ import annotations

from functools import lru_cache, partial
from logging import getLogger
from typing import Generator, Iterable, Set

from apluggy import contextmanager

from nextline.process.callback.spec import hookimpl
from nextline.process.callback.types import TraceArgs
from nextline.utils import match_any


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


class AddModuleToTrace:
    '''Let Python modules be traced in new threads and asyncio tasks.'''

    def __init__(self, modules_to_trace: Set[str]):
        self._modules_to_trace = modules_to_trace
        self._logger = getLogger(__name__)

    @hookimpl
    @contextmanager
    def cmdloop(self, trace_args: TraceArgs) -> Generator[None, str, None]:
        frame, _, _ = trace_args
        if module_name := frame.f_globals.get('__name__'):
            msg = f'{self.__class__.__name__}: adding {module_name!r}'
            self._logger.info(msg)
            self._modules_to_trace.add(module_name)
        yield
