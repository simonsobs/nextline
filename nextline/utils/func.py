from threading import Thread, current_thread
from asyncio import Task, current_task, get_running_loop

from typing import Union


def current_task_or_thread() -> Union[Task, Thread]:
    try:
        task = current_task()
    except RuntimeError:
        task = None
    return task or current_thread()


try:
    from asyncio import to_thread
except ImportError:
    # for Python 3.8
    # to_thread() is new in Python 3.9

    async def to_thread(func):
        loop = get_running_loop()
        await loop.run_in_executor(None, func)
