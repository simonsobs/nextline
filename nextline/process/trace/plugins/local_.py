from __future__ import annotations

from collections import defaultdict
from logging import getLogger
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, DefaultDict, Dict, Optional, Set

from apluggy import PluginManager, contextmanager

from nextline.count import PromptNoCounter
from nextline.process.exc import NotOnTraceCall
from nextline.process.pdb.custom import CustomizedPdb
from nextline.process.pdb.proxy import WithContext
from nextline.process.pdb.stream import StdInOut
from nextline.process.trace.spec import hookimpl
from nextline.process.trace.types import TraceArgs
from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, TraceNo

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class LocalTraceFunc:
    def __init__(self) -> None:
        self._map: DefaultDict[TraceNo, TraceFunc] = defaultdict(self._create)

    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._hook = hook
        self._command_queue_map = command_queue_map

        self._callback = Callback(
            hook=self._hook,
            command_queue_map=self._command_queue_map,
        )
        self._cmdloop_hook = CmdloopHook(hook=self._hook)

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

        stdio = StdInOut(prompt_func=self._callback.prompt)

        pdb = CustomizedPdb(
            cmdloop_hook=self._cmdloop_hook,
            stdin=stdio,
            stdout=stdio,
        )
        stdio.prompt_end = pdb.prompt

        trace = pdb.trace_dispatch

        trace = TraceCallContext(trace=trace, hook=self._hook)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace


class TraceCallHandler:
    def __init__(self) -> None:
        self._trace_args_map: Dict[TraceNo, TraceArgs] = {}
        self._traces_on_call: Set[TraceNo] = set()

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    @contextmanager
    def trace_call(self, trace_args: TraceArgs):
        trace_no = self._hook.hook.current_trace_no()
        self._traces_on_call.add(trace_no)
        self._trace_args_map[trace_no] = trace_args
        try:
            yield
        finally:
            self._traces_on_call.remove(trace_no)
            del self._trace_args_map[trace_no]

    @hookimpl
    def is_on_trace_call(self) -> Optional[bool]:
        trace_no = self._hook.hook.current_trace_no()
        return trace_no in self._traces_on_call

    @hookimpl
    def current_trace_args(self) -> Optional[TraceArgs]:
        trace_no = self._hook.hook.current_trace_no()
        return self._trace_args_map.get(trace_no)


def TraceCallContext(trace: TraceFunc, hook: PluginManager) -> TraceFunc:
    def _context(frame, event, arg):
        return hook.with_.trace_call(trace_args=(frame, event, arg))

    return WithContext(trace, context=_context)


def CmdloopHook(hook: PluginManager):
    def cmdloop():
        if not hook.hook.is_on_trace_call():
            raise NotOnTraceCall
        return hook.with_.cmdloop()

    return cmdloop


class Callback:
    def __init__(
        self,
        hook: PluginManager,
        command_queue_map: CommandQueueMap,
    ):
        self._hook = hook
        self._command_queue_map = command_queue_map
        self._prompt_no_counter = PromptNoCounter(1)
        self._logger = getLogger(__name__)

    def prompt(self, text: str) -> str:
        prompt_no = self._prompt_no_counter()
        self._logger.debug(f'PromptNo: {prompt_no}')
        with (p := self._hook.with_.prompt(prompt_no=prompt_no, out=text)):
            command = self._get_command(prompt_no=prompt_no)
            p.gen.send(command)
        return command

    def _get_command(self, prompt_no: PromptNo) -> str:
        trace_no = self._hook.hook.current_trace_no()
        self._logger.debug(f'PromptNo: {prompt_no}')
        queue = self._command_queue_map[trace_no]

        while True:
            command, prompt_no_, trace_no_ = queue.get()
            try:
                assert trace_no_ == trace_no
            except AssertionError:
                msg = f'TraceNo mismatch: {trace_no_} != {trace_no}'
                self._logger.exception(msg)
                raise
            if not prompt_no_ == prompt_no:
                self._logger.warning(f'PromptNo mismatch: {prompt_no_} != {prompt_no}')
                continue
            return command
