import sys
from typing import List
from unittest.mock import Mock, call

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nextline.utils import peek_stderr, peek_stdout


@given(
    msgs=st.lists(st.text(), max_size=10),
    post_msg=st.text(),
    errs=st.lists(st.text(), max_size=10),
    post_err=st.text(),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_print(
    capsys: pytest.CaptureFixture,
    msgs: List[str],
    post_msg: str,
    errs: List[str],
    post_err: str,
):
    capsys.readouterr()  # clear

    callback_out = Mock()
    callback_err = Mock()

    with peek_stdout(callback_out):
        with peek_stderr(callback_err):
            for m in msgs:
                print(m)
            for e in errs:
                print(e, file=sys.stderr)
    print(post_msg)
    print(post_err, file=sys.stderr)

    expected_calls_out = [call(s) for m in msgs for s in (m, '\n')]
    assert expected_calls_out == callback_out.call_args_list

    expected_calls_err = [call(s) for e in errs for s in (e, '\n')]
    assert expected_calls_err == callback_err.call_args_list

    captured = capsys.readouterr()

    expected_captured_out = ''.join(f'{m}\n' for m in msgs) + f'{post_msg}\n'
    assert expected_captured_out == captured.out

    expected_captured_err = ''.join(f'{e}\n' for e in errs) + f'{post_err}\n'
    assert expected_captured_err == captured.err


@given(
    msgs=st.lists(st.text(), max_size=10),
    errs=st.lists(st.text(), max_size=10),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_yield(
    capsys: pytest.CaptureFixture,
    msgs: List[str],
    errs: List[str],
):
    capsys.readouterr()  # clear

    callback_out = Mock()
    callback_err = Mock()

    with peek_stdout(callback_out) as stdout_write:
        with peek_stderr(callback_err) as stderr_write:
            for m in msgs:
                stdout_write(m)
            for e in errs:
                stderr_write(e)

    expected_calls_out = [call(m) for m in msgs]
    assert expected_calls_out == callback_out.call_args_list

    expected_calls_err = [call(e) for e in errs]
    assert expected_calls_err == callback_err.call_args_list

    captured = capsys.readouterr()
    assert ''.join(msgs) == captured.out
    assert ''.join(errs) == captured.err


def test_raise(capsys: pytest.CaptureFixture):
    callback = Mock(side_effect=MockError)

    with peek_stdout(callback):
        with pytest.raises(MockError):
            print('foo')

    print('bar')

    assert [call('foo')] == callback.call_args_list

    captured = capsys.readouterr()
    assert 'bar\n' == captured.out


class MockError(BaseException):
    pass
