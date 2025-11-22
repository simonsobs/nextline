import time
from threading import Thread, current_thread
from typing import Any, Callable, Optional, Set

from nextline.utils.thread_exception import ExcThread


class ThreadDoneCallback:
    """Call a function when each registered thread ends

    Parameters
    ----------
    done : callable, optional
        A function with one arg. Each time a registered thread ends, this
        function will be called with the thread object as the arg. The return
        value will be ignored.

        The `done` is optional. This class can be still useful to wait for all
        registered tasks to end.

    interval : float, default 0.001 [sec]
        The period of determining if any registered thread ends.
    """

    def __init__(
        self,
        done: Optional[Callable[[Thread], Any]] = None,
        interval: float = 0.001,
    ):
        self._done = done
        self._interval = interval

        self._active: Set[Thread] = set()
        self._closed = False

        self._t = ExcThread(target=self._monitor, daemon=True)
        self._t.start()

    def register(self, thread: Optional[Thread] = None) -> Thread:
        """Add the current thread by default, or the given thread

        The callback function `done`, given at the initialization,
        will be called with the thread object when the thread ends.
        """
        if thread is None:
            thread = current_thread()
        self._active.add(thread)
        return thread

    def close(self) -> None:
        """To be optionally called after all threads are registered

        This method returns after all registered threads end.

        The method cannot be called from a registered thread.

        If exceptions are raised in the callback function, this method
        re-raises the first exception.

        """
        if current_thread() in self._active:
            raise RuntimeError("The close() cannot be called from a registered thread")
        self._closed = True
        self._t.join()

    def _monitor(self) -> None:
        exc = []
        while True:
            if done := {t for t in self._active if not t.is_alive()}:
                if self._done:
                    for d in done:
                        try:
                            self._done(d)
                        except BaseException as e:
                            exc.append(e)
                self._active = self._active - done
            time.sleep(self._interval)
            if self._active:
                continue
            if self._closed:
                break
        if exc:
            raise exc[0]

    def __enter__(self) -> "ThreadDoneCallback":
        return self

    def __exit__(self, exc_type, exc_value, traceback):  # type: ignore
        del exc_type, exc_value, traceback
        self.close()
