import pytest

from nextline import wrap


SOURCE = """
x = 0
""".strip()


def test_simple():
    code = compile(SOURCE, "<string>", "exec")
    func = wrap.compose(code)
    func()


SOURCE_MODULE_NAME = """
print(__name__)
""".strip()


def test_module_name(capsys):
    # Use stdout to receive data from code
    code = compile(SOURCE_MODULE_NAME, "<string>", "exec")
    func = wrap.compose(code)
    func()
    actual = capsys.readouterr().out.strip()
    # with capsys.disabled():
    #     print(actual)
    expected = wrap.__name__
    assert expected == actual


SOURCE_IMPORT = """
import time
def f():
    time.sleep(0.01)
f()
"""


def test_import():
    """Assert that the issue is resolved
    https://github.com/simonsobs/nextline/issues/7
    """
    code = compile(SOURCE_IMPORT, "<string>", "exec")
    func = wrap.compose(code)
    func()


def test_import_error_demonstration():
    """Show the issue
    https://github.com/simonsobs/nextline/issues/7

    The NameError occurs if the second arg (globals) is not given to
    exec(). An empty dict resolves the issue. Read the doc for the
    detail: https://docs.python.org/3/library/functions.html#exec
    """
    code = compile(SOURCE_IMPORT, "<string>", "exec")
    with pytest.raises(NameError):
        exec(code)
    exec(code, {})
