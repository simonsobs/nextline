import time
from asyncio import Task, current_task, to_thread
from typing import Any, Callable, Optional


class TaskDoneCallback:
    """Call a function when each registered asyncio task ends

    Parameters
    ----------
    done : callable, optional
        A function with one arg. Each time a registered asyncio task ends, this
        function will be called with the task object as the arg. The return
        value will be ignored.

        The `done` is optional. This class can be still useful to wait for all
        registered tasks to end.
    """

    def __init__(self, done: Optional[Callable[[Task], Any]] = None):
        self._done = done
        self._active = set[Task]()
        self._exceptions = list[BaseException]()

    def register(self, task: Optional[Task] = None) -> Task:
        """Add the current task by default, or the given task

        The callback function `done`, given at the initialization,
        will be called with the task object when the task ends.
        """
        if task is None:
            task = current_task()
            if task is None:
                raise RuntimeError("The current task not found")
        if task not in self._active:
            task.add_done_callback(self._callback)
            self._active.add(task)
        return task

    def close(self, interval: float = 0.001) -> None:
        """To be optionally called after all tasks are registered

        This method returns after all registered tasks end.

        The method cannot be called from a registered task.

        If exceptions are raised in the callback function, this method
        re-raises the first exception.

        """
        try:
            task = current_task()
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
        task = current_task()
        if task is not None:
            if task in self._active:
                raise RuntimeError(
                    "The aclose() cannot be called from a registered task"
                )
        await to_thread(self._close, interval)
        self.reraise()

    def reraise(self) -> None:
        """Reraise the first exception occurred in the callback function"""
        if self._exceptions:
            raise self._exceptions[0]

    def _close(self, interval: float) -> None:
        while self._active:
            time.sleep(interval)

    def _callback(self, task: Task, *_: Any, **__: Any) -> None:
        """This method is given to asyncio.Task.add_done_callback()

        When called, this method, in turn, calls the callback function
        `done`, given at the initialization.

        Note: This method will be called by asyncio.Handle with the
        task object as the only argument. However, the method is
        accepting additional arbitrary arguments because an exception
        caused by an argument mismatch will be difficult to find; it
        will be caught by the asyncio.Handle and given to the
        exception handler of the event loop.
        """

        try:
            self._active.remove(task)
            if self._done:
                self._done(task)
        except BaseException as e:
            self._exceptions.append(e)

    def __enter__(self) -> "TaskDoneCallback":
        return self

    def __exit__(self, exc_type, exc_value, traceback):  # type: ignore
        del exc_type, exc_value, traceback
        self.close()

    async def __aenter__(self) -> "TaskDoneCallback":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):  # type: ignore
        del exc_type, exc_value, traceback
        await self.aclose()
