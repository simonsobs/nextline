import time
import random
from threading import Thread

from nextline.utils import ThreadDoneCallback
from nextline.utils import ExcThread

import pytest
from unittest.mock import Mock


def target(obj: ThreadDoneCallback):
    """To run in a thread"""
    obj.register()
    delay = random.random() * 0.01
    time.sleep(delay)


class Done:
    """A callback function"""

    def __init__(self):
        self.args = set()

    def __call__(self, arg):
        self.args.add(arg)


@pytest.fixture()
def done():
    """A callback function"""
    yield Done()


def test_one(done: Done):
    obj = ThreadDoneCallback(done=done)
    t = Thread(target=target, args=(obj,))
    t.start()
    obj.close()
    assert {t} == done.args
    t.join()


def test_register_arg(done: Done):
    def target():
        delay = random.random() * 0.01
        time.sleep(delay)

    obj = ThreadDoneCallback(done=done)
    t = Thread(target=target)

    # manually provide the thread object
    obj.register(t)

    t.start()
    obj.close()
    assert {t} == done.args
    t.join()


def test_daemon(done: Done):
    """Not blocked even if close() is not called"""
    obj = ThreadDoneCallback(done=done)
    t = Thread(target=target, args=(obj,))
    t.start()
    # obj.close()  # not call closed()
    t.join()


@pytest.mark.parametrize("nthreads", [0, 1, 2, 5, 10])
def test_multiple(nthreads: int, done: Done):

    obj = ThreadDoneCallback(done=done)

    threads = {Thread(target=target, args=(obj,)) for _ in range(nthreads)}
    for t in threads:
        t.start()

    obj.close()
    assert threads == done.args

    for t in threads:
        t.join()


def test_raise_close_from_thread(done: Done):
    def target(obj: ThreadDoneCallback):
        obj.register()

        obj.close()
        # raised originally here, then reraised at the join() by
        # ExcThread in the main thread.

    obj = ThreadDoneCallback(done=done)
    t = ExcThread(target=target, args=(obj,))
    t.start()
    with pytest.raises(RuntimeError):
        t.join()


def test_raise_in_done():
    done = Mock(side_effect=ValueError)
    obj = ThreadDoneCallback(done=done)
    t = Thread(target=target, args=(obj,))
    t.start()

    with pytest.raises(ValueError):
        obj.close()

    t.join()


def test_interval(done: Done):
    interval = 0.02
    obj = ThreadDoneCallback(done=done, interval=interval)
    t = Thread(target=target, args=(obj,))
    t.start()

    obj.close()
    t.join()


def test_interval_invalid(done: Done):
    interval = "invalid"
    obj = ThreadDoneCallback(done=done, interval=interval)
    t = Thread(target=target, args=(obj,))
    t.start()

    with pytest.raises(TypeError):
        obj.close()

    t.join()
