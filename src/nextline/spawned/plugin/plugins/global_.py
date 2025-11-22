from logging import getLogger
from types import FrameType
from typing import Any, Optional

from apluggy import PluginManager

from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import TraceFunction


class TraceFuncCreator:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook
        self._logger = getLogger(__name__)

    @hookimpl
    def create_trace_func(self) -> TraceFunction:
        def _trace_func(
            frame: FrameType, event: str, arg: Any
        ) -> Optional[TraceFunction]:
            try:
                return self._hook.hook.global_trace_func(
                    frame=frame, event=event, arg=arg
                )
            except BaseException:
                self._logger.exception('')
                raise

        return _trace_func


class GlobalTraceFunc:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def global_trace_func(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunction]:
        if self._hook.hook.filter(trace_args=(frame, event, arg)):
            return None
        self._hook.hook.filtered(trace_args=(frame, event, arg))
        return self._hook.hook.local_trace_func(frame=frame, event=event, arg=arg)
