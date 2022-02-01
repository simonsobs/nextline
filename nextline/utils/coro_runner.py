import asyncio
from typing import Coroutine, Awaitable, Union


##__________________________________________________________________||
class CoroutineRunner:
    """Execute the coroutine in the asyncio event loop at the instantiation

    A running asyncio event loop needs to exist in the thread in which this
    class is instantiated. The method run() can be called in any thread,
    regardless of whether the same thread in which this class is instantiated or
    any other thread. In either case, the coroutine given to run() will be
    executed in the event loop in the thread in which this class is
    instantiated.

    This class can be useful when you need to run coroutines in the asyncio
    event loop in a particular thread but events that require the coroutines to
    run can occur any threads.
    """

    def __init__(self):
        self.loop = asyncio.get_running_loop()

    def __repr__(self):
        # e.g., "<CoroutineRunner loop=<_UnixSelectorEventLoop running=True closed=False debug=False>>"
        return f"<{self.__class__.__name__} loop={self.loop!r}>"

    def run(self, coro: Coroutine) -> Union[Awaitable, None]:
        """Schedule or execute the coroutine

        If this method is called in the same thread as the one in which this
        class was instantizted, return the asyncio task for the coroutine. If in
        a different thread, schedule to run in the thread at the instantiation,
        wait until it exits, and return None.

        Parameters
        ----------
        coro : Coroutine
            The coroutine to be executed

        Returns
        -------
        Task or None
            The task for the coroutine if in the same thread as of the
            instantiation of this class. None, otherwise.
        """

        if self._is_the_same_running_loop():
            return asyncio.create_task(coro)

        if self.loop.is_closed():
            # The loop that was running when this class
            # was inntantizted is closed.
            raise RuntimeError(f"The loop is closed: {self.loop}")

        # In another thread

        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        fut.result()

    def _is_the_same_running_loop(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        return self.loop is loop


##__________________________________________________________________||
