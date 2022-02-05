import pytest

from nextline.state import Initialized


SOURCE = """
import time
time.sleep(0.001)
""".strip()


@pytest.mark.asyncio
async def test_register_state_name():
    state = Initialized(SOURCE)
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = await state.close()

    expected = ["initialized", "running", "exited", "finished", "closed"]
    actual = [
        c.args[1]
        for c in state.registry.register.call_args_list
        if c.args[0] == "state_name"
    ]
    assert expected == actual


@pytest.mark.asyncio
async def test_register_state_name_reset():
    state = Initialized(SOURCE)
    state = state.reset()
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = state.reset()
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = await state.close()

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
        for c in state.registry.register.call_args_list
        if c.args[0] == "state_name"
    ]
    assert expected == actual

    state = state.reset()
    state = state.run()
    state = await state.exited()
    state = await state.finish()
    state = await state.close()

    expected = ["initialized", "running", "exited", "finished", "closed"]
    actual = [
        c.args[1]
        for c in state.registry.register.call_args_list
        if c.args[0] == "state_name"
    ]
    assert expected == actual
