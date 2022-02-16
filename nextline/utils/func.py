from threading import Thread, current_thread
from asyncio import Task, current_task

from typing import Union


def current_task_or_thread() -> Union[Task, Thread]:
    try:
        task = current_task()
    except RuntimeError:
        task = None
    return task or current_thread()
