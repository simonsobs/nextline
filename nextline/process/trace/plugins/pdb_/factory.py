from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from apluggy import PluginManager

from nextline.count import PromptNoCounter
from nextline.process.exc import NotOnTraceCall
from nextline.process.pdb.custom import CustomizedPdb
from nextline.process.pdb.stream import PromptFuncType, StdInOut
from nextline.process.trace.spec import hookimpl

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
