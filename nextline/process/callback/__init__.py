from __future__ import annotations

from logging import getLogger
from types import FrameType
from typing import TYPE_CHECKING, Optional

from nextline.process.types import CommandQueueMap
from nextline.types import RunNo

from .hook import build_hook
from .plugins import RegistrarProxy

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class Callback:
    def __init__(
        self,
        run_no: RunNo,
        registrar: RegistrarProxy,
        command_queue_map: CommandQueueMap,
    ):
        self._hook = build_hook(run_no, registrar, command_queue_map)
        self._logger = getLogger(__name__)

    def global_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        try:
            return self._hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
        except BaseException:
            self._logger.exception('')
            raise

    def start(self) -> None:
        self._hook.hook.start()

    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._hook.hook.close(
            exc_type=exc_type, exc_value=exc_value, traceback=traceback
        )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close(exc_type, exc_value, traceback)
