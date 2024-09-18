from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, call

from hypothesis import given, settings
from hypothesis import strategies as st
from transitions import MachineError

from nextline.fsm import Callback, StateMachine
from nextline.types import ResetOptions


class StatefulTest:
    def __init__(self) -> None:
        self._callback = AsyncMock(spec=Callback)
        self._machine = StateMachine(callback=self._callback)
        pass

    @asynccontextmanager
    async def context(self) -> AsyncIterator[None]:
        self._prev = self._machine.state
        self._callback.reset_mock()
        try:
            yield
        except MachineError:
            assert self._machine.state == self._prev
        repr(self._machine)

    async def initialize(self) -> None:
        # Always raise MachineError as already initialized by __aenter__.
        await self._machine.initialize()
        # self.assert_after_initialize()

    def assert_after_initialize(self) -> None:
        assert self._callback.mock_calls == [
            call.start(),
            call.initialize_run(),
            call.on_change_state('initialized'),
        ]
        self._callback.start.assert_awaited_once()
        self._callback.initialize_run.assert_awaited_once()

    async def run(self) -> None:
        await self._machine.run()
        assert self._callback.mock_calls == [
            call.start_run(),
            call.on_change_state('running'),
        ]
        self._callback.start_run.assert_awaited_once()

    async def finish(self) -> None:
        await self._machine.finish()
        assert self._callback.mock_calls == [
            call.finish(),
            call.on_change_state('finished'),
        ]

    async def reset(self) -> None:
        options = ResetOptions()
        await self._machine.reset(reset_options=options)
        if self._prev == 'finished':
            assert self._callback.mock_calls == [
                call.reset(reset_options=options),
                call.on_exit_finished(),
                call.initialize_run(),
                call.on_change_state('initialized'),
            ]
            self._callback.on_exit_finished.assert_awaited_once()
        else:
            assert self._callback.mock_calls == [
                call.reset(reset_options=options),
                call.initialize_run(),
                call.on_change_state('initialized'),
            ]
        self._callback.reset.assert_awaited_once()
        self._callback.initialize_run.assert_awaited_once()

    async def close(self) -> None:
        await self._machine.close()
        self.assert_after_close()

    def assert_after_close(self) -> None:
        if self._prev == 'running':
            assert self._callback.mock_calls == [
                call.wait_for_run_finish(),
                call.close(),
                call.on_change_state('closed'),
            ]
            self._callback.wait_for_run_finish.assert_awaited_once()
            self._callback.close.assert_awaited_once()
        elif self._prev == 'finished':
            assert self._callback.mock_calls == [
                call.on_exit_finished(),
                call.close(),
                call.on_change_state('closed'),
            ]
            self._callback.on_exit_finished.assert_awaited_once()
            self._callback.close.assert_awaited_once()
        elif self._prev == 'closed':
            assert self._callback.mock_calls == []
        else:
            assert self._callback.mock_calls == [
                call.close(),
                call.on_change_state('closed'),
            ]
            self._callback.close.assert_awaited_once()


    async def __aenter__(self) -> 'StatefulTest':
        async with self.context():
            await self._machine.__aenter__()
            self.assert_after_initialize()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> bool:
        async with self.context():
            handled = await self._machine.__aexit__(*args, **kwargs)  # type: ignore
            self.assert_after_close()
        return bool(handled)


@settings(max_examples=200)
@given(data=st.data())
async def test_property(data: st.DataObject) -> None:
    test = StatefulTest()

    METHODS = [
        test.initialize,
        test.run,
        test.finish,
        test.reset,
        test.close,
    ]

    methods = data.draw(st.lists(st.sampled_from(METHODS)))

    async with test:
        for method in methods:
            async with test.context():
                await method()
