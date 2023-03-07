from __future__ import annotations

from logging import getLogger
from types import FrameType
from typing import TYPE_CHECKING, Optional

from apluggy import PluginManager

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class Callback:
    def __init__(self, hook: PluginManager):
        self._hook = hook
        self._logger = getLogger(__name__)

    def global_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        try:
            return self._hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
        except BaseException:
            self._logger.exception('')
            raise

    def start(self) -> None:
        self._hook.hook.start()
        self._logger.info(f'{self.__class__.__name__}: started the hook')

    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._hook.hook.close(
            exc_type=exc_type, exc_value=exc_value, traceback=traceback
        )
        self._logger.info(f'{self.__class__.__name__}: closed the hook')

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close(exc_type, exc_value, traceback)
