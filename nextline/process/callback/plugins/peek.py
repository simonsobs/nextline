from __future__ import annotations

from asyncio import Task
from threading import Thread
from typing import TYPE_CHECKING, Set

from nextline.process.callback.spec import hookimpl
from nextline.process.io import peek_stdout_by_task_and_thread
from nextline.utils import current_task_or_thread

if TYPE_CHECKING:
    from nextline.process.callback import Callback


class PeekStdout:
    def __init__(self, callback: 'Callback') -> None:
        self._callback = callback
        self._tasks_and_threads: Set[Task | Thread] = set()

    @hookimpl
    def task_or_thread_start(self) -> None:
        task_or_thread = current_task_or_thread()
        self._tasks_and_threads.add(task_or_thread)

    @hookimpl
    def start(self) -> None:
        self._peek_stdout = peek_stdout_by_task_and_thread(
            to_peek=self._tasks_and_threads, callback=self._callback.stdout
        )
        self._peek_stdout.__enter__()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._peek_stdout.__exit__(exc_type, exc_value, traceback)
