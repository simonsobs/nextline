from __future__ import annotations

from logging import getLogger
from queue import Queue

from apluggy import PluginManager

from nextline.spawned.trace.spec import hookimpl
from nextline.spawned.types import CommandQueueMap
from nextline.types import PromptNo, TraceNo


class Prompt:
    '''A plugin that responds to the hook prompt() with commands from a queue.'''

    def __init__(self) -> None:
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._hook = hook
        self._command_queue_map = command_queue_map

    @hookimpl
    def on_start_trace(self, trace_no: TraceNo) -> None:
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
