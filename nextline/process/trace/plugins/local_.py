from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Callable, DefaultDict, Dict, Optional, Set

from apluggy import PluginManager

from nextline.count import PromptNoCounter
from nextline.process.exc import TraceNotCalled
from nextline.process.pdb.proxy import TraceCallCallback, instantiate_pdb
from nextline.process.trace.spec import hookimpl
from nextline.process.trace.types import TraceArgs
from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, TraceNo

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class LocalTraceFunc:
    def __init__(self) -> None:
        self._prompt_no_counter = PromptNoCounter(1)
        self._map: DefaultDict[TraceNo, TraceFunc] = defaultdict(self._create)

    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._hook = hook
        self._command_queue_map = command_queue_map

        self._callback = Callback(
            hook=self._hook,
            command_queue_map=self._command_queue_map,
            prompt_no_counter=self._prompt_no_counter,
        )

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:
        self._command_queue_map[trace_no] = Queue()

    @hookimpl
    def trace_end(self, trace_no: TraceNo) -> None:
        del self._command_queue_map[trace_no]

    @hookimpl
    def local_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        trace_no = self._hook.hook.current_trace_no()
        local_trace_func = self._map[trace_no]
        return local_trace_func(frame, event, arg)

    def _create(self) -> TraceFunc:

        trace = instantiate_pdb(callback=self._callback)

        trace = TraceCallCallback(trace=trace, callback=self._callback)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace


class Callback:
    def __init__(
        self,
        hook: PluginManager,
        command_queue_map: CommandQueueMap,
        prompt_no_counter: Callable[[], PromptNo],
    ):
        self._hook = hook
        self._command_queue_map = command_queue_map
        self._prompt_no_counter = prompt_no_counter

        self._trace_args_map: Dict[TraceNo, TraceArgs] = {}

        self._logger = getLogger(__name__)

        self._traces_on_call: Set[TraceNo] = set()

    def _is_on_call(self) -> bool:
        trace_no = self._hook.hook.current_trace_no()
        return trace_no in self._traces_on_call

    @contextmanager
    def trace_call(self, trace_args: TraceArgs):
        trace_no = self._hook.hook.current_trace_no()
        self._traces_on_call.add(trace_no)
        self._trace_args_map[trace_no] = trace_args

        with self._hook.with_.trace_call(trace_no=trace_no, trace_args=trace_args):
            try:
                yield
            finally:
                self._traces_on_call.remove(trace_no)
                del self._trace_args_map[trace_no]

    @contextmanager
    def cmdloop(self):
        if not self._is_on_call():
            raise TraceNotCalled
        trace_no = self._hook.hook.current_trace_no()
        trace_args = self._trace_args_map[trace_no]
        with self._hook.with_.cmdloop(trace_no=trace_no, trace_args=trace_args):
            yield

    def prompt(self, text: str) -> str:
        trace_no = self._hook.hook.current_trace_no()
        trace_args = self._trace_args_map[trace_no]
        prompt_no = self._prompt_no_counter()
        self._logger.debug(f'PromptNo: {prompt_no}')
        queue = self._command_queue_map[trace_no]
        with (
            p := self._hook.with_.prompt(
                trace_no=trace_no,
                prompt_no=prompt_no,
                trace_args=trace_args,
                out=text,
            )
        ):
            while True:
                command, prompt_no_, trace_no_ = queue.get()
                try:
                    assert trace_no_ == trace_no
                except AssertionError:
                    msg = f'TraceNo mismatch: {trace_no_} != {trace_no}'
                    self._logger.exception(msg)
                    raise
                if prompt_no_ == prompt_no:
                    break
                self._logger.warning(f'PromptNo mismatch: {prompt_no_} != {prompt_no}')
            p.gen.send(command)
        return command
