__all__ = ['register']

from apluggy import PluginManager

from nextline.spawned.types import RunArg

from .compose import CallableComposer
from .concurrency import TaskAndThreadKeeper, TaskOrThreadToTraceMapper
from .filter import FilerByModule, FilterByModuleName, FilterLambda, FilterMainScript
from .global_ import GlobalTraceFunc, TraceFuncCreator
from .local_ import LocalTraceFunc, TraceCallHandler
from .pdb_ import PdbInstanceFactory, Prompt
from .peek import PeekStdout
from .repeat import Repeater


def register(hook: PluginManager, run_arg: RunArg) -> None:
    hook.register(Repeater)
    hook.register(PeekStdout)
    hook.register(Prompt)
    hook.register(PdbInstanceFactory)
    hook.register(TraceCallHandler)
    hook.register(LocalTraceFunc)
    hook.register(TaskOrThreadToTraceMapper)
    hook.register(TaskAndThreadKeeper)
    if run_arg.trace_modules:
        hook.register(FilerByModule)
        hook.register(FilterLambda)
        hook.register(FilterByModuleName)
    else:
        hook.register(FilterLambda)
        hook.register(FilterMainScript)
    hook.register(GlobalTraceFunc)
    hook.register(TraceFuncCreator)
    hook.register(CallableComposer)
