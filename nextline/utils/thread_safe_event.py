import asyncio

from .loop import ToLoop


class ThreadSafeAsyncioEvent(asyncio.Event):
    """A thread-safe asyncio event

    The methods set() and clear() can be called from any threads. The method
    wait() needs to be called in the thread in which this class is
    instantiated.

    Code originally copied from https://stackoverflow.com/a/33006667/7309855

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._to_loop = ToLoop()

    def set(self):
        return self._to_loop(super().set)

    def clear(self):
        return self._to_loop(super().clear)
