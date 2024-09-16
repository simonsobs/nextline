from typing import NoReturn

import pytest

from nextline.utils import ExcThread


class ErrorInThread(Exception):
    pass


def func_raise() -> NoReturn:
    raise ErrorInThread()


def test_return() -> None:
    t = ExcThread(target=func_raise)
    t.start()
    with pytest.raises(ErrorInThread):
        t.join()
