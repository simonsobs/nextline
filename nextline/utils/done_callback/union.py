from __future__ import annotations
from threading import Thread
from asyncio import Task

from typing import Callable, Optional, Any

from ..func import current_task_or_thread, to_thread
from .thread import ThreadDoneCallback
from .task import TaskDoneCallback


class ThreadTaskDoneCallback:
    def __init__(
        self,
        done: Optional[Callable[[Task | Thread], Any]] = None,
        interval: float = 0.001,
    ):
        self._thread_callback = ThreadDoneCallback(
            done=done, interval=interval
        )
        self._task_callback = TaskDoneCallback(done=done)

    def register(
        self, task_or_thread: Optional[Task | Thread] = None
    ) -> Task | Thread:
        if task_or_thread is None:
            task_or_thread = current_task_or_thread()
        if isinstance(task_or_thread, Task):
            self._task_callback.register(task_or_thread)
        else:
            self._thread_callback.register(task_or_thread)
        return task_or_thread

    def close(self, interval: float = 0.001) -> None:
        self._task_callback.close(interval=interval)
        self._thread_callback.close()

    async def aclose(self, interval: float = 0.001) -> None:
        """Awaitable version of close()"""
        await self._task_callback.aclose(interval=interval)
        await to_thread(self._thread_callback.close)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.aclose()
