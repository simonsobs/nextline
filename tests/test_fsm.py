from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from rich import print
from transitions import Machine, MachineError
from transitions.extensions.markup import MarkupMachine

from nextline.fsm import build_state_machine


def test_model_default():
    machine = build_state_machine()
    assert not machine.models
    print(machine.models)


def test_model_self_literal():
    machine = build_state_machine(model=Machine.self_literal)
    assert machine.models[0] is machine
    assert len(machine.models) == 1


async def test_transitions() -> None:

    # created -- initialize() --> initialized
    machine = build_state_machine(model=Machine.self_literal)
    machine.on_reset = AsyncMock()  # type: ignore
    assert machine.is_created()
    await machine.initialize()
    assert machine.is_initialized()

    # initialized -- reset() --> initialized
    assert machine.is_initialized()
    await machine.reset()
    assert machine.on_reset.call_count == 1
    assert machine.on_reset.await_count == 1
    machine.on_reset.reset_mock()
    assert machine.is_initialized()

    # initialized -- run() --> running -- finish() --> finished -- reset() --> initialized
    assert machine.is_initialized()
    await machine.run()
    assert machine.is_running()
    await machine.finish()
    assert machine.is_finished()
    await machine.reset()
    assert machine.on_reset.call_count == 1
    assert machine.on_reset.await_count == 1
    machine.on_reset.reset_mock()
    assert machine.is_initialized()

    # initialized -- run() --> running -- finish() --> finished -- close() --> closed
    assert machine.is_initialized()
    await machine.run()
    assert machine.is_running()
    await machine.finish()
    assert machine.is_finished()
    await machine.close()
    assert machine.is_closed()

    # created -- close() --> closed
    machine = build_state_machine(model=Machine.self_literal)
    assert machine.is_created()
    await machine.close()
    assert machine.is_closed()

    # created -- initialize() -> initialized -- close() --> closed
    machine = build_state_machine(model=Machine.self_literal)
    assert machine.is_created()
    await machine.initialize()
    assert machine.is_initialized()
    await machine.close()
    assert machine.is_closed()


# @pytest.mark.skip
async def test_invalid_triggers() -> None:

    machine = build_state_machine(model=Machine.self_literal)
    assert machine.is_created()
    await machine.initialize()
    assert machine.is_initialized()
    await machine.run()
    assert machine.is_running()

    # running -- close() -- invalid
    with pytest.raises(MachineError):
        await machine.close()

    assert machine.is_running()

    # running -- reset() -- invalid
    with pytest.raises(MachineError):
        await machine.reset()

    assert machine.is_running()


def test_restore_from_markup():
    machine = build_state_machine(model=None, markup=True)
    assert isinstance(machine.markup, dict)
    markup = deepcopy(machine.markup)
    del markup['models']
    rebuild = MarkupMachine(model=None, **markup)
    assert rebuild.markup == machine.markup


@pytest.mark.skip
def test_graph():
    machine = build_state_machine(model=Machine.self_literal, graph=True)
    machine.get_graph().draw('states.png', prog='dot')
