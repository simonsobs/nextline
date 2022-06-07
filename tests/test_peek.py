from __future__ import annotations
import sys

import pytest
from unittest.mock import MagicMock, Mock, call

from nextline.peek import peek_stdout_write, peek_stderr_write


def test_stdout(capsys):
    callback = MagicMock()

    with peek_stdout_write(callback):
        print("foo")

    print("bar")

    # with capsys.disabled():
    #     print(callback.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list
    assert [call()] == callback.__enter__.call_args_list
    assert [call(None, None, None)] == callback.__exit__.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.out


def test_stderr(capsys):
    callback = MagicMock()

    with peek_stderr_write(callback):
        print("foo", file=sys.stderr)

    print("bar", file=sys.stderr)

    # with capsys.disabled():
    #     print(callback.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list
    assert [call()] == callback.__enter__.call_args_list
    assert [call(None, None, None)] == callback.__exit__.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.err


def test_stdout_target(capsys):
    callback = MagicMock()

    with peek_stdout_write(callback) as t:
        t("foo")

    assert [call("foo")] == callback.call_args_list
    assert [call()] == callback.__enter__.call_args_list
    assert [call(None, None, None)] == callback.__exit__.call_args_list

    captured = capsys.readouterr()
    assert "foo" == captured.out


def test_stderr_target(capsys):
    callback = MagicMock()

    with peek_stderr_write(callback) as t:
        t("foo")

    assert [call("foo")] == callback.call_args_list
    assert [call()] == callback.__enter__.call_args_list
    assert [call(None, None, None)] == callback.__exit__.call_args_list

    captured = capsys.readouterr()
    assert "foo" == captured.err


def test_raise(capsys):
    callback = MagicMock(side_effect=MockCallError)

    with peek_stdout_write(callback):
        with pytest.raises(MockCallError):
            print("foo")

    print("bar")

    assert [call("foo")] == callback.call_args_list
    assert [call()] == callback.__enter__.call_args_list
    assert [call(None, None, None)] == callback.__exit__.call_args_list

    captured = capsys.readouterr()
    assert "bar\n" == captured.out


def test_raise_close(capsys):
    callback = MagicMock()
    callback.__exit__ = Mock(side_effect=MockCloseError)

    with pytest.raises(MockCloseError):
        with peek_stdout_write(callback):
            print("foo")

    print("bar")

    # with capsys.disabled():
    #     print(callback.call_args_list)
    #     print(callback.close.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list
    assert [call()] == callback.__enter__.call_args_list
    assert [call(None, None, None)] == callback.__exit__.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.out


class MockCallError(BaseException):
    pass


class MockCloseError(BaseException):
    pass
