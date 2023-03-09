from __future__ import annotations
from collections import defaultdict

from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Callable, DefaultDict, Dict, Optional, Tuple

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

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:
        command_queue: Queue[Tuple[str, PromptNo, TraceNo]] = Queue()
        self._command_queue_map[trace_no] = command_queue

    @hookimpl
    def trace_end(self, trace_no: TraceNo) -> None:
        del self._command_queue_map[trace_no]

    @hookimpl
    def local_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        local_trace_func = self._get_local_trace_func()
        return local_trace_func(frame, event, arg)

    def _get_local_trace_func(self) -> TraceFunc:
        trace_no = self._hook.hook.current_trace_no()
        local_trace_func = self._map[trace_no]
        return local_trace_func

    def _create(self) -> TraceFunc:
        trace_no = self._hook.hook.current_trace_no()
        callback = CallbackForTrace(
            trace_no=trace_no,
            hook=self._hook,
            command_queue=self._command_queue_map[trace_no],
            prompt_no_counter=self._prompt_no_counter,
        )

        trace = instantiate_pdb(callback=callback)

        trace = TraceCallCallback(trace=trace, callback=callback)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace


class CallbackForTrace:
    def __init__(
        self,
        trace_no: TraceNo,
        hook: PluginManager,
        command_queue: Queue[Tuple[str, PromptNo, TraceNo]],
        prompt_no_counter: Callable[[], PromptNo],
    ):
        self._trace_no = trace_no
        self._hook = hook
        self._prompt_no_counter = prompt_no_counter

        self._command_queue = command_queue
        self._trace_args: TraceArgs | None = None

        self._logger = getLogger(__name__)

    @contextmanager
    def trace_call(self, trace_args: TraceArgs):
        self._trace_args = trace_args
        with self._hook.with_.trace_call(
            trace_no=self._trace_no, trace_args=trace_args
        ):
            try:
                yield
            finally:
                self._trace_args = None

    @contextmanager
    def cmdloop(self):
        if self._trace_args is None:
            raise TraceNotCalled
        with self._hook.with_.cmdloop(
            trace_no=self._trace_no, trace_args=self._trace_args
        ):
            yield

    def prompt(self, text: str) -> str:
        prompt_no = self._prompt_no_counter()
        self._logger.debug(f'PromptNo: {prompt_no}')
        with (
            p := self._hook.with_.prompt(
                trace_no=self._trace_no,
                prompt_no=prompt_no,
                trace_args=self._trace_args,
                out=text,
            )
        ):
            while True:
                command, prompt_no_, trace_no_ = self._command_queue.get()
                try:
                    assert trace_no_ == self._trace_no
                except AssertionError:
                    msg = f'TraceNo mismatch: {trace_no_} != {self._trace_no}'
                    self._logger.exception(msg)
                    raise
                if prompt_no_ == prompt_no:
                    break
                self._logger.warning(f'PromptNo mismatch: {prompt_no_} != {prompt_no}')
            p.gen.send(command)
        return command
