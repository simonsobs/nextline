__all__ = ['register']


from apluggy import PluginManager

from .compose import CallableComposer
from .concurrency import TaskAndThreadKeeper, TaskOrThreadToTraceMapper
from .filter import FilerByModule, FilterByModuleName, FilterLambda
from .global_ import GlobalTraceFunc, TraceFuncCreator
from .local_ import LocalTraceFunc, TraceCallHandler
from .pdb_ import PdbInstanceFactory, Prompt
from .peek import PeekStdout
from .repeat import Repeater


def register(hook: PluginManager) -> None:
    hook.register(Repeater)
    hook.register(PeekStdout)
    hook.register(Prompt)
    hook.register(PdbInstanceFactory)
    hook.register(TraceCallHandler)
    hook.register(LocalTraceFunc)
    hook.register(TaskOrThreadToTraceMapper)
    hook.register(TaskAndThreadKeeper)
    hook.register(FilerByModule)
    hook.register(FilterLambda)
    hook.register(FilterByModuleName)
    hook.register(GlobalTraceFunc)
    hook.register(TraceFuncCreator)
    hook.register(CallableComposer)
