import time
from queue import Queue
from typing import Optional

from .timer import Timer


def wait_until_queue_empty(
    queue: Queue, timeout: Optional[float] = None, interval: float = 0.001
) -> None:
    '''Wait until the queue is empty.

    Parameters
    ----------
    queue :
        The queue to wait for.
    timeout : optional
        The timeout in seconds. Wait indefinitely if None.
    interval : float, optional
        The interval in seconds to check the queue.

    '''
    if timeout is None:
        while not queue.empty():
            time.sleep(interval)
    else:
        timer = Timer(timeout)
        while not queue.empty():
            if timer.is_timeout():
                raise TimeoutError(f'Timeout. the queue is not empty: {queue!r}')
            time.sleep(interval)
