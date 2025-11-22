from logging import getLogger
from typing import Any, Callable, ContextManager

from apluggy import PluginManager

from nextline.count import PromptNoCounter
from nextline.spawned.exc import NotOnTraceCall
from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import TraceFunction

from .custom import CustomizedPdb
from .stream import PromptFuncType, StdInOut


class PdbInstanceFactory:
    '''A plugin that creates local trace functions.

    Each time the first result only hook `create_local_trace_func` is called,
    this plugin creates a new instance of the customized Pdb class and returns
    its trace function.

    The hook `create_local_trace_func` is called for each async task or thread.
    '''

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._factory = Factory(hook=hook)

    @hookimpl
    def create_local_trace_func(self) -> TraceFunction:
        return self._factory()


def Factory(hook: PluginManager) -> Callable[[], TraceFunction]:
    cmdloop_hook = CmdloopHook(hook=hook)
    prompt_func = PromptFunc(hook=hook)

    def _factory() -> TraceFunction:
        stdio = StdInOut(prompt_func=prompt_func)
        pdb = CustomizedPdb(
            cmdloop_hook=cmdloop_hook,
            stdin=stdio,
            stdout=stdio,
        )
        stdio.prompt_end = pdb.prompt
        return pdb.trace_dispatch

    return _factory


def CmdloopHook(hook: PluginManager) -> Callable[[], ContextManager[Any]]:
    '''Return a context manager in which Pdb.cmdloop() is called.'''

    def cmdloop() -> ContextManager[Any]:
        if not hook.hook.is_on_trace_call():
            raise NotOnTraceCall
        return hook.with_.on_cmdloop()

    return cmdloop


def PromptFunc(hook: PluginManager) -> PromptFuncType:
    '''Return a function that responds to Pdb prompts with user commands.'''

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
