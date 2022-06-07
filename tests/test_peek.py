from __future__ import annotations
import sys

import pytest
from unittest.mock import Mock, call

from nextline.peek import peek_stdout_write, peek_stderr_write


def test_stdout(capsys):
    callback = Mock()

    with peek_stdout_write(callback):
        print("foo")

    print("bar")

    # with capsys.disabled():
    #     print(callback.call_args_list)
    #     print(callback.close.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list
    assert [call()] == callback.close.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.out


def test_stderr(capsys):
    callback = Mock()

    with peek_stderr_write(callback):
        print("foo", file=sys.stderr)

    print("bar", file=sys.stderr)

    # with capsys.disabled():
    #     print(callback.call_args_list)
    #     print(callback.close.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list
    assert [call()] == callback.close.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.err


def test_raise(capsys):
    callback = Mock(side_effect=MockCallError)

    with peek_stdout_write(callback):
        with pytest.raises(MockCallError):
            print("foo")

    print("bar")

    # with capsys.disabled():
    #     print(callback.call_args_list)
    #     print(callback.close.call_args_list)

    assert [call("foo")] == callback.call_args_list
    assert [call()] == callback.close.call_args_list

    captured = capsys.readouterr()
    assert "bar\n" == captured.out


def test_raise_close(capsys):
    callback = Mock()
    callback.close = Mock(side_effect=MockCloseError)

    with pytest.raises(MockCloseError):
        with peek_stdout_write(callback):
            print("foo")

    print("bar")

    # with capsys.disabled():
    #     print(callback.call_args_list)
    #     print(callback.close.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list
    assert [call()] == callback.close.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.out


class MockCallError(BaseException):
    pass


class MockCloseError(BaseException):
    pass
