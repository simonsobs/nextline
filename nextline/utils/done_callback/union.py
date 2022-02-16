from threading import Thread, current_thread
from asyncio import Task, current_task, to_thread, get_running_loop


from typing import Union, Callable

from .thread import ThreadDoneCallback
from .task import TaskDoneCallback


class ThreadTaskDoneCallback:
    def __init__(
        self,
        done: Callable[[Union[Task, Thread]], None],
        interval: float = 0.001,
    ):
        self._thread_callback = ThreadDoneCallback(
            done=done, interval=interval
        )
        self._task_callback = TaskDoneCallback(done=done)

    def register(
        self, task_or_thread: Union[Task, Thread, None] = None
    ) -> None:
        if task_or_thread is None:
            task_or_thread = self._current_task_or_thread()
        if isinstance(task_or_thread, Task):
            self._task_callback.register(task_or_thread)
            return
        self._thread_callback.register(task_or_thread)

    def close(self, interval: float = 0.001) -> None:
        self._task_callback.close(interval=interval)
        self._thread_callback.close()

    async def aclose(self, interval: float = 0.001) -> None:
        """Awaitable version of close()"""
        await self._task_callback.aclose(interval=interval)

        func = self._thread_callback.close
        try:
            await to_thread(func)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = get_running_loop()
            await loop.run_in_executor(None, func)

    def _current_task_or_thread(self) -> Union[Task, Thread]:
        try:
            task = current_task()
        except RuntimeError:
            task = None
        return task or current_thread()
