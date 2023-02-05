import atexit
import sys
from concurrent.futures.process import _python_exit
from typing import Any, Callable, List


def suppress_atexit_oserror():
    '''Catch the OS error at exit in Python 3.8

    The following error can occur at the end of the pytest in Python 3.8:

      Error in atexit._run_exitfuncs:
      Traceback (most recent call last):
        File ...
          ...
        File "... lib/python3.8/multiprocessing/connection.py", line 136, in _check_closed
          raise OSError("handle is closed")
      OSError: handle is closed

    This function is used as a fixture to suppress the error.

    Usage:
      Add the following code to the conftest.py file:

        import pytest
        from nextline.test import suppress_atexit_oserror
        _ = pytest.fixture(scope='session', autouse=True)(suppress_atexit_oserror)


    Reference: https://stackoverflow.com/q/68091084/7309855

    '''
    yield
    if sys.version_info >= (3, 9):
        return

    if not _atexit_is_registered(_python_exit):
        return

    atexit.unregister(_python_exit)
    atexit.register(_wrap_python_exit)


def _wrap_python_exit(*args, **kwargs):
    try:
        _python_exit(*args, **kwargs)
    except OSError:
        pass


def _atexit_is_registered(func: Callable[..., Any]) -> bool:
    return func in _atexit_registered()


def _atexit_registered() -> List[Callable[..., Any]]:
    # https://stackoverflow.com/a/63813607/7309855
    import atexit

    ret = []

    class Capture:
        def __eq__(self, other):
            ret.append(other)
            return False

        def __call__(self):
            pass

    c = Capture()
    atexit.unregister(c)
    return ret
