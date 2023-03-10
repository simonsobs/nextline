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
from nextline.process.pdb.stream import PromptFuncType, StdInOut
from nextline.process.trace.spec import hookimpl
from nextline.process.trace.types import TraceArgs
from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, TraceNo

from .with_ import WithContext

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class LocalTraceFunc:
    def __init__(self) -> None:
        self._map: DefaultDict[TraceNo, TraceFunc] = defaultdict(self._create)
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._hook = hook
        self._command_queue_map = command_queue_map

        self._cmdloop_hook = CmdloopHook(hook=self._hook)
        self._prompt_func = PromptFunc(hook=self._hook)

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

        stdio = StdInOut(prompt_func=self._prompt_func)

        pdb = CustomizedPdb(
            cmdloop_hook=self._cmdloop_hook,
            stdin=stdio,
            stdout=stdio,
        )
        stdio.prompt_end = pdb.prompt

        trace = TraceCallContext(trace=pdb.trace_dispatch, hook=self._hook)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace

    @hookimpl
    def prompt(self, prompt_no: PromptNo) -> str:
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


def PromptFunc(hook: PluginManager) -> PromptFuncType:

    counter = PromptNoCounter(1)
    logger = getLogger(__name__)

    def _prompt_func(text: str) -> str:
        prompt_no = counter()
        logger.debug(f'PromptNo: {prompt_no}')
        with (context := hook.with_.on_prompt(prompt_no=prompt_no, text=text)):
            command = hook.hook.prompt(prompt_no=prompt_no, text=text)
            if command is None:
                logger.warning(f'command is None: {command!r}')
            context.gen.send(command)
        return command

    return _prompt_func
