import asyncio
from unittest.mock import AsyncMock, call

import pytest
from transitions import MachineError

from nextline.context import Context
from nextline.fsm.state import Machine


def test_repr(context: Context) -> None:
    obj = Machine(context=context)
    assert repr(obj)


async def test_callbacks_transitions(context: AsyncMock) -> None:

    event = asyncio.Event()

    async def finish():
        await event.wait()

    context.finish.side_effect = finish

    obj = Machine(context=context)

    async with obj:

        # initialized -- reset() --> initialized

        assert obj.is_initialized()  # type: ignore
        expected_calls = [call.initialize(), call.state_change('initialized')]
        assert expected_calls == context.method_calls
        context.reset_mock()

        await obj.reset(10, foo='bar')  # type: ignore
        assert obj.is_initialized()  # type: ignore
        expected_calls = [
            call.reset(10, foo='bar'),
            call.initialize(),
            call.state_change('initialized'),
        ]
        assert expected_calls == context.method_calls
        context.reset_mock()

        # initialized -- run() --> running -- finish() --> finished -- reset() --> initialized

        await obj.run()  # type: ignore
        assert obj.is_running()  # type: ignore
        await asyncio.sleep(0.001)
        expected_calls = [call.run(), call.finish(), call.state_change('running')]
        assert expected_calls == context.method_calls
        context.reset_mock()

        event.set()
        await obj._event_finished.wait()

        assert obj.is_finished()  # type: ignore
        expected_calls = [call.state_change('finished')]
        assert expected_calls == context.method_calls
        context.reset_mock()

        await obj.reset(10, foo='bar')  # type: ignore
        assert obj.is_initialized()  # type: ignore
        expected_calls = [
            call.reset(10, foo='bar'),
            call.initialize(),
            call.state_change('initialized'),
        ]
        assert expected_calls == context.method_calls
        context.reset_mock()

    assert obj.is_closed()  # type: ignore
    expected_calls = [call.close(), call.state_change('closed')]
    assert expected_calls == context.method_calls


async def test_signals(context: AsyncMock) -> None:

    event = asyncio.Event()

    async def finish():
        await event.wait()

    context.finish.side_effect = finish

    obj = Machine(context=context)

    await obj.to_running()  # type: ignore
    assert obj.is_running()  # type: ignore

    context.reset_mock()

    await obj.interrupt()  # type: ignore
    expected_calls = [call.interrupt()]
    assert expected_calls == context.method_calls
    context.reset_mock()

    await obj.terminate()  # type: ignore
    expected_calls = [call.terminate()]
    assert expected_calls == context.method_calls
    context.reset_mock()

    await obj.kill()  # type: ignore
    expected_calls = [call.kill()]
    assert expected_calls == context.method_calls
    context.reset_mock()

    event.set()
    await obj._event_finished.wait()

    await obj.close()  # type: ignore


async def test_signals_raised(context: AsyncMock) -> None:
    obj = Machine(context=context)

    for state in obj._machine.states:
        if state == 'running':
            continue
        obj._machine.set_state(state)
        assert obj.state == state  # type: ignore

        with pytest.raises(MachineError):
            await obj.interrupt()  # type: ignore

        with pytest.raises(MachineError):
            await obj.terminate()  # type: ignore

        with pytest.raises(MachineError):
            await obj.kill()  # type: ignore


class MockException(BaseException):
    pass


async def test_results(context: AsyncMock) -> None:
    obj = Machine(context=context)

    await obj.to_finished()  # type: ignore
    assert obj.is_finished()  # type: ignore

    context.reset_mock()

    exc = MockException()
    context.exception.return_value = exc
    assert exc == obj.exception()

    context.exception.return_value = None
    result = object()
    context.result.return_value = result
    assert result == obj.result()


async def test_results_raised(context: AsyncMock) -> None:
    obj = Machine(context=context)

    for state in obj._machine.states:
        if state == 'finished':
            continue
        obj._machine.set_state(state)
        assert obj.state == state  # type: ignore

        with pytest.raises(AssertionError):
            obj.exception()

        with pytest.raises(AssertionError):
            obj.result()


@pytest.fixture
def context() -> AsyncMock:
    y = AsyncMock(spec=Context)
    return y
