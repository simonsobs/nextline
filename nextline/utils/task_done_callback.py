import time
import asyncio
from functools import partial

from typing import Optional, Callable, Type, Set, List


class TaskDoneCallback:
    """Call a function when each registered asyncio task ends

    Parameters
    ----------
    done : callable
        A function with one arg. Each time a registered asyncio task
        ends, this function will be called with the task object as
        the arg. The return value will be ignored.
    """

    def __init__(
        self,
        done: Callable[[asyncio.Task], None],
    ):
        self._done = done
        self._active: Set[asyncio.Task] = set()
        self._exceptions: List[Type[Exception]] = []

    def register(self, task: Optional[asyncio.Task] = None) -> None:
        """Add the current task by default, or the given task

        The callback function `done`, given at the initializaiton,
        will be called with the task object when the task ends.
        """
        if task is None:
            task = asyncio.current_task()
            if task is None:
                raise RuntimeError("The current task not found")
        if task not in self._active:
            task.add_done_callback(self._callback)
            self._active.add(task)

    def close(self, interval: float = 0.001) -> None:
        """To be optionally called after all tasks are registered

        This method returns after all registered tasks end.

        The method cannot be called from a registered task.

        If exceptions are raised in the callback funciton, this method
        reraises the first exception.

        """
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        if task is not None:
            if task in self._active:
                raise RuntimeError(
                    "The close() cannot be called from a registered task"
                )
        self._close(interval)
        self.reraise()

    async def aclose(self, interval: float = 0.001) -> None:
        """Awaitable version of close()"""
        task = asyncio.current_task()
        if task is not None:
            if task in self._active:
                raise RuntimeError(
                    "The aclose() cannot be called from a registered task"
                )
        func = partial(self._close, interval)
        try:
            await asyncio.to_thread(func)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, func)
        self.reraise()

    def reraise(self) -> None:
        """Reraise the first excpeption occured in the callback function"""
        if self._exceptions:
            raise self._exceptions[0]

    def _close(self, interval):
        while self._active:
            time.sleep(interval)

    def _callback(self, task: asyncio.Task, *_, **__):
        """This method is given to asyncio.Task.add_done_callback()

        When called, this method, in turn, calls the callback function
        `done`, given at the initializaiton.

        Note: This method will be called by asyncio.Handle with the
        task object as the only argument. However, the method is
        accepting additonal arbitrary arguments because an exception
        caused by an argument mismatch will be difficult to find; it
        will be catched by the asyncio.Handle and given to the
        exception handler of the event loop.
        """

        try:
            self._active.remove(task)
            self._done(task)
        except BaseException as e:
            self._exceptions.append(e)
