import time
import random
from threading import current_thread

from nextline.utils import ThreadDoneCallback
from nextline.utils import ExcThread

import pytest
from unittest.mock import Mock


def target(obj: ThreadDoneCallback):
    """To run in a thread"""
    assert current_thread() == obj.register()
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


def test_close(done: Done):
    obj = ThreadDoneCallback(done=done)
    t = ExcThread(target=target, args=(obj,))
    t.start()
    time.sleep(0.005)
    obj.close()
    assert {t} == done.args
    t.join()


def test_with(done: Done):
    with ThreadDoneCallback(done=done) as obj:
        t = ExcThread(target=target, args=(obj,))
        t.start()
        time.sleep(0.005)
    assert {t} == done.args
    t.join()


def test_register_arg(done: Done):
    def target():
        delay = random.random() * 0.01
        time.sleep(delay)

    with ThreadDoneCallback(done=done) as obj:
        t = ExcThread(target=target)

        # manually provide the thread object
        assert t == obj.register(t)

        t.start()
        time.sleep(0.005)

    assert {t} == done.args
    t.join()


def test_daemon(done: Done):
    """Not blocked even if close() is not called"""
    obj = ThreadDoneCallback(done=done)
    t = ExcThread(target=target, args=(obj,))
    t.start()
    time.sleep(0.005)
    # obj.close()  # not call closed()
    t.join()


@pytest.mark.parametrize("n_threads", [0, 1, 2, 5, 10])
def test_multiple(n_threads: int, done: Done):

    with ThreadDoneCallback(done=done) as obj:

        threads = {
            ExcThread(target=target, args=(obj,)) for _ in range(n_threads)
        }
        for t in threads:
            t.start()
        time.sleep(0.005)

    assert threads == done.args

    for t in threads:
        t.join()


def test_raise_close_from_thread(done: Done):
    def target(obj: ThreadDoneCallback):
        obj.register()

        obj.close()
        # raised originally here, then re-raised at the join() by
        # ExcThread in the main thread.

    obj = ThreadDoneCallback(done=done)
    t = ExcThread(target=target, args=(obj,))
    t.start()
    with pytest.raises(RuntimeError):
        t.join()


def test_raise_in_done():
    done = Mock(side_effect=ValueError)
    obj = ThreadDoneCallback(done=done)
    t = ExcThread(target=target, args=(obj,))
    t.start()
    time.sleep(0.005)

    with pytest.raises(ValueError):
        obj.close()

    t.join()


def test_interval(done: Done):
    interval = 0.02
    obj = ThreadDoneCallback(done=done, interval=interval)
    t = ExcThread(target=target, args=(obj,))
    t.start()
    time.sleep(0.005)

    obj.close()
    t.join()


def test_done_none():
    with ThreadDoneCallback() as obj:
        t = ExcThread(target=target, args=(obj,))
        t.start()
        time.sleep(0.005)
    assert not t.is_alive()
    t.join()
