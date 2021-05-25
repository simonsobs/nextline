import asyncio

##__________________________________________________________________||
class CoroutineRunner:
    """Run a coroutine in the loop.
    """
    def __init__(self):
        self.loop = asyncio.get_running_loop()

    def run(self, coro):
        """Run a coroutine in the loop.

        Return a task if in the loop. If not in the loop, schedule to
        run in the loop and wait until it exits.

        """

        if self._is_the_same_running_loop():
            return asyncio.create_task(coro)

        # not in the loop, i.e., in another thread

        if self.loop.is_closed():
            # The loop in the main thread is closed.
            warnings.warn(f'The loop is closed: {self.loop}')
            return

        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        fut.result()

    def _is_the_same_running_loop(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        return self.loop is loop

##__________________________________________________________________||
