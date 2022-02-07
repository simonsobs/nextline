import itertools

import pytest

from unittest.mock import Mock

from nextline.state import Initialized
from nextline.utils import Registry


SOURCE = """
import time
time.sleep(0.001)
""".strip()


@pytest.fixture()
async def registry():
    y = Mock(spec=Registry, wraps=Registry())
    y.open_register("statement")
    y.open_register("state_name")
    y.open_register("run_no")
    y.open_register("run_no_count")
    y.register("run_no_count", itertools.count().__next__)
    y.register("statement", SOURCE)
    yield y
    await y.close()


@pytest.mark.asyncio
async def test_register_state_name(registry):
    state = Initialized(registry=registry)
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = state.close()

    expected = ["initialized", "running", "exited", "finished", "closed"]
    actual = [
        c.args[1]
        for c in registry.register.call_args_list
        if c.args[0] == "state_name"
    ]
    assert expected == actual


@pytest.mark.asyncio
async def test_register_state_name_reset(registry):
    state = Initialized(registry=registry)
    state = state.reset()
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = state.reset()
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = state.close()

    expected = [
        "initialized",
        "initialized",
        "running",
        "exited",
        "finished",
        "initialized",
        "running",
        "exited",
        "finished",
        "closed",
    ]
    actual = [
        c.args[1]
        for c in registry.register.call_args_list
        if c.args[0] == "state_name"
    ]
    assert expected == actual
