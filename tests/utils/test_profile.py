import re

from nextline.utils import profile_func


def test_one() -> None:
    def func() -> int:
        re.compile("foo|bar")
        return 123

    result, ret = profile_func(func)
    assert result
    assert ret == 123
