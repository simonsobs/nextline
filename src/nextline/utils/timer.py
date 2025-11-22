import time


class Timer:
    '''A timer.

    Parameters
    ----------
    timeout :
        The timeout in seconds. If None, it never times out.


    Examples
    --------
    >>> timer = Timer(timeout=0.01)
    >>> timer.elapsed() < 0.01
    True

    >>> timer.is_timeout()
    False

    >>> timer.restart()

    >>> timer.is_timeout()
    False

    >>> time.sleep(0.01)

    >>> timer.is_timeout()
    True

    >>> timer = Timer(timeout=None)
    >>> time.sleep(0.03)
    >>> timer.is_timeout()
    False

    '''

    def __init__(self, timeout: float | None) -> None:
        self._timeout = timeout
        self._start = time.perf_counter()

    def restart(self) -> None:
        '''Restart the timer.'''
        self._start = time.perf_counter()

    def elapsed(self) -> float:
        '''Return the time passed in seconds.'''
        return time.perf_counter() - self._start

    def is_timeout(self) -> bool:
        '''Return True if the timeout is reached.'''
        if self._timeout is None:
            return False
        return self.elapsed() > self._timeout
