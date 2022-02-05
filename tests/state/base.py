from abc import ABC, abstractmethod

import pytest

from nextline.state import Initialized, StateObsoleteError, StateMethodError

SOURCE_ONE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


class BaseTestState(ABC):
    @pytest.fixture()
    def statement(self):
        yield SOURCE_ONE

    @pytest.fixture()
    async def initialized(self, statement):
        y = Initialized(statement)
        yield y
        if y.is_obsolete():
            return
        await y.close()

    @pytest.fixture()
    async def running(self, initialized):
        y = initialized.run()
        yield y
        if y.is_obsolete():
            return
        exited = await y.exited()
        if exited.is_obsolete():
            return
        finished = await exited.finish()
        await finished.close()

    @pytest.fixture()
    async def exited(self, running):
        y = await running.exited()
        yield y
        if y.is_obsolete():
            return
        finished = await y.finish()
        await finished.close()

    @pytest.fixture()
    async def finished(self, exited):
        y = await exited.finish()
        yield y
        if y.is_obsolete():
            return
        await y.close()

    @pytest.fixture()
    async def closed(self, finished):
        y = await finished.close()
        yield y

    @abstractmethod
    def state(self, *_, **__):
        pass

    params = (pytest.param(SOURCE_TWO, id="SOURCE_TWO"), None)

    @pytest.fixture(params=params)
    def statements_for_test_reset(self, statement, request):
        old_statement = statement
        statement = request.param
        if statement:
            expected_statement = statement
        else:
            expected_statement = old_statement
        yield (expected_statement, statement)

    def test_state(self, state):
        assert isinstance(state, self.state_class)
        assert "obsolete" not in repr(state)

    async def assert_obsolete(self, state):
        assert "obsolete" in repr(state)

        with pytest.raises(StateObsoleteError):
            state.run()

        with pytest.raises(StateObsoleteError):
            await state.exited()

        with pytest.raises(StateObsoleteError):
            await state.finish()

        with pytest.raises(StateObsoleteError):
            state.reset()

        with pytest.raises(StateObsoleteError):
            await state.close()

    def test_run(self, state):
        with pytest.raises(StateMethodError):
            state.run()

    @pytest.mark.asyncio
    async def test_exited(self, state):
        with pytest.raises(StateMethodError):
            await state.exited()

    @pytest.mark.asyncio
    async def test_finish(self, state):
        with pytest.raises(StateMethodError):
            await state.finish()

    @pytest.mark.asyncio
    async def test_reset(self, state, statements_for_test_reset):
        _t, statement = statements_for_test_reset

        with pytest.raises(StateMethodError):
            state.reset(statement=statement)

    def test_send_pdb_command(self, state):
        thread_asynctask_id = (1, None)
        command = "next"
        with pytest.raises(StateMethodError):
            state.send_pdb_command(thread_asynctask_id, command)

    def test_exception(self, state):
        with pytest.raises(StateMethodError):
            state.exception()

    def test_result(self, state):
        with pytest.raises(StateMethodError):
            state.result()
