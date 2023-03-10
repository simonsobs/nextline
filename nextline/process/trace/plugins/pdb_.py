from __future__ import annotations

from logging import getLogger
from queue import Queue
from typing import TYPE_CHECKING

from apluggy import PluginManager

from nextline.count import PromptNoCounter
from nextline.process.exc import NotOnTraceCall
from nextline.process.pdb.custom import CustomizedPdb
from nextline.process.pdb.stream import PromptFuncType, StdInOut
from nextline.process.trace.spec import hookimpl
from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, TraceNo

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class PdbInstanceFactory:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._cmdloop_hook = CmdloopHook(hook=hook)
        self._prompt_func = PromptFunc(hook=hook)

    @hookimpl
    def create_local_trace_func(self) -> TraceFunc:
        stdio = StdInOut(prompt_func=self._prompt_func)
        pdb = CustomizedPdb(
            cmdloop_hook=self._cmdloop_hook,
            stdin=stdio,
            stdout=stdio,
        )
        stdio.prompt_end = pdb.prompt
        return pdb.trace_dispatch


class Prompt:
    def __init__(self) -> None:
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._hook = hook
        self._command_queue_map = command_queue_map

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:
        self._command_queue_map[trace_no] = Queue()

    @hookimpl
    def trace_end(self, trace_no: TraceNo) -> None:
        del self._command_queue_map[trace_no]

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
