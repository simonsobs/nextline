import asyncio


##__________________________________________________________________||
class ThreadSafeAsyncioEvent(asyncio.Event):
    """A thread-safe asyncio event

    The methods set() and clear() can be called from any threads. The method
    wait() needs to be called in the thread in which this class is instantiated.

    Code originally copied from https://stackoverflow.com/a/33006667/7309855

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._loop is None:  # Python 3.10
            self._loop = asyncio.get_event_loop()

    def set(self):
        return self._exec_threadsafe(super().set)

    def clear(self):
        return self._exec_threadsafe(super().clear)

    def _exec_threadsafe(self, func):
        if self._in_the_same_loop():
            return func()

        async def afunc(func):
            return func()

        fut = asyncio.run_coroutine_threadsafe(afunc(func), self._loop)
        return fut.result()

    def _in_the_same_loop(self):
        try:
            return self._loop is asyncio.get_running_loop()
        except RuntimeError:
            return False


##__________________________________________________________________||
