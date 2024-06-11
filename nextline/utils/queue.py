import time
from queue import Queue
from typing import Optional

from .timer import Timer


class WaitUntilQueueEmptyTimeout(Exception):
    '''Raised if the queue is not empty within the timeout.'''


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
    timer = Timer(timeout)
    while not queue.empty():
        if timer.is_timeout():
            raise WaitUntilQueueEmptyTimeout(
                f'Timed out after {timeout} seconds. The queue is not empty: {queue!r}'
            )
        time.sleep(interval)
