from typing import Optional

from apluggy import PluginManager

from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import TraceFunction


class GlobalTraceFunc:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def global_trace_func(self, frame, event, arg) -> Optional[TraceFunction]:
        if self._hook.hook.filter(trace_args=(frame, event, arg)):
            return None
        self._hook.hook.filtered(trace_args=(frame, event, arg))
        return self._hook.hook.local_trace_func(frame=frame, event=event, arg=arg)
