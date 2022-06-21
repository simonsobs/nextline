from __future__ import annotations

import re

from nextline.utils import profile_func


def test_one():
    def func():
        re.compile("foo|bar")
        return 123

    result, ret = profile_func(func)
    assert result
    assert ret == 123
