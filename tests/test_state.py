from unittest.mock import Mock, call

import pytest

from nextline.context import Context
from nextline.state import Machine


def test_repr(context: Context) -> None:
    model = Machine(context=context)
    assert repr(model)


async def test_callbacks_transitions(context: Mock) -> None:
    model = Machine(context=context)

    async with model:

        # initialized -- reset() --> initialized

        assert model.is_initialized()  # type: ignore
        expected_calls = [call.initialize(), call.state_change('initialized')]
        assert expected_calls == context.method_calls
        context.reset_mock()

        await model.reset(10, foo='bar')  # type: ignore
        assert model.is_initialized()  # type: ignore
        expected_calls = [
            call.reset(10, foo='bar'),
            call.initialize(),
            call.state_change('initialized'),
        ]
        assert expected_calls == context.method_calls
        context.reset_mock()

        # initialized -- run() --> running -- finish() --> finished -- reset() --> initialized

        await model.run()  # type: ignore
        assert model.is_running()  # type: ignore
        expected_calls = [call.run(), call.state_change('running')]
        assert expected_calls == context.method_calls
        context.reset_mock()

        await model.finish()  # type: ignore
        assert model.is_finished()  # type: ignore
        expected_calls = [call.finish(), call.state_change('finished')]
        assert expected_calls == context.method_calls
        context.reset_mock()

        await model.reset(10, foo='bar')  # type: ignore
        assert model.is_initialized()  # type: ignore
        expected_calls = [
            call.reset(10, foo='bar'),
            call.initialize(),
            call.state_change('initialized'),
        ]
        assert expected_calls == context.method_calls
        context.reset_mock()

    assert model.is_closed()  # type: ignore
    expected_calls = [call.close(), call.state_change('closed')]
    assert expected_calls == context.method_calls


async def test_signals(context: Mock) -> None:
    model = Machine(context=context)

    await model.to_running()  # type: ignore
    assert model.is_running()  # type: ignore

    context.reset_mock()

    model.interrupt()
    expected_calls = [call.interrupt()]
    assert expected_calls == context.method_calls
    context.reset_mock()

    model.terminate()
    expected_calls = [call.terminate()]
    assert expected_calls == context.method_calls
    context.reset_mock()

    model.kill()
    expected_calls = [call.kill()]
    assert expected_calls == context.method_calls
    context.reset_mock()


async def test_signals_raised(context: Mock) -> None:
    model = Machine(context=context)

    for state in model._machine.states:
        if state == 'running':
            continue
        model._machine.set_state(state)
        assert model.state == state  # type: ignore

        with pytest.raises(AssertionError):
            model.interrupt()

        with pytest.raises(AssertionError):
            model.terminate()

        with pytest.raises(AssertionError):
            model.kill()


class MockException(BaseException):
    pass


async def test_results(context: Mock) -> None:
    model = Machine(context=context)

    await model.to_finished()  # type: ignore
    assert model.is_finished()  # type: ignore

    context.reset_mock()

    exc = MockException()
    context.exception = exc
    assert exc == model.exception()

    with pytest.raises(MockException):
        model.result()

    context.exception = None
    result = object()
    context.result = result
    assert result == model.result()


async def test_results_raised(context: Mock) -> None:
    model = Machine(context=context)

    for state in model._machine.states:
        if state == 'finished':
            continue
        model._machine.set_state(state)
        assert model.state == state  # type: ignore

        with pytest.raises(AssertionError):
            model.exception()

        with pytest.raises(AssertionError):
            model.result()


@pytest.fixture
def context() -> Mock:
    y = Mock(spec=Context)
    y.exception = None
    return y
