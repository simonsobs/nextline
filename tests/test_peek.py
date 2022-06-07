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

    assert [call("foo"), call("\n")] == callback.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.out


def test_stderr(capsys):
    callback = Mock()

    with peek_stderr_write(callback):
        print("foo", file=sys.stderr)

    print("bar", file=sys.stderr)

    # with capsys.disabled():
    #     print(callback.call_args_list)

    assert [call("foo"), call("\n")] == callback.call_args_list

    captured = capsys.readouterr()
    assert "foo\nbar\n" == captured.err


def test_stdout_target(capsys):
    callback = Mock()

    with peek_stdout_write(callback) as t:
        t("foo")

    assert [call("foo")] == callback.call_args_list

    captured = capsys.readouterr()
    assert "foo" == captured.out


def test_stderr_target(capsys):
    callback = Mock()

    with peek_stderr_write(callback) as t:
        t("foo")

    assert [call("foo")] == callback.call_args_list

    captured = capsys.readouterr()
    assert "foo" == captured.err


def test_raise(capsys):
    callback = Mock(side_effect=MockError)

    with peek_stdout_write(callback):
        with pytest.raises(MockError):
            print("foo")

    print("bar")

    assert [call("foo")] == callback.call_args_list

    captured = capsys.readouterr()
    assert "bar\n" == captured.out


class MockError(BaseException):
    pass
