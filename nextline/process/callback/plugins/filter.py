from __future__ import annotations

from logging import getLogger
from typing import Generator, Set

from apluggy import contextmanager

from nextline.process.callback.spec import hookimpl
from nextline.process.callback.types import TraceArgs


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
