from copy import deepcopy
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from transitions import Machine, MachineError
from transitions.extensions.markup import MarkupMachine

from nextline.fsm.factory import build_state_machine


def test_model_default():
    machine = build_state_machine()
    assert not machine.models


def test_model_self_literal():
    machine = build_state_machine(model=Machine.self_literal)
    assert machine.models[0] is machine
    assert len(machine.models) == 1


def test_restore_from_markup():
    machine = build_state_machine(model=None, markup=True)
    assert isinstance(machine.markup, dict)
    markup = deepcopy(machine.markup)

    del markup['models']

    # add missing 'dest' for internal transitions
    for transition in markup['transitions']:
        if 'dest' not in transition:
            transition['dest'] = None

    rebuild = MarkupMachine(model=None, **markup)
    assert rebuild.markup == machine.markup


@pytest.mark.skip
def test_graph():
    machine = build_state_machine(model=Machine.self_literal, graph=True)
    machine.get_graph().draw('states.png', prog='dot')


async def test_invalid_triggers() -> None:

    machine = build_state_machine(model=Machine.self_literal)
    await machine.initialize()
    await machine.run()
    assert machine.is_running()

    # running -- reset() -- invalid
    with pytest.raises(MachineError):
        await machine.reset()

    assert machine.is_running()


async def test_transitions_manual() -> None:

    # created -- initialize() --> initialized
    machine = build_state_machine(model=Machine.self_literal)
    machine.on_reset = AsyncMock()  # type: ignore
    assert machine.is_created()
    await machine.initialize()
    assert machine.is_initialized()

    # initialized -- reset() --> initialized
    await machine.reset()
    assert machine.on_reset.call_count == 1
    assert machine.on_reset.await_count == 1
    machine.on_reset.reset_mock()
    assert machine.is_initialized()

    # initialized -- run() --> running -- finish() --> finished -- close() --> closed
    await machine.run()
    assert machine.is_running()
    await machine.finish()
    assert machine.is_finished()
    await machine.close()
    assert machine.is_closed()


@st.composite
def st_paths(draw: st.DrawFn):
    max_n_paths = 30

    state_map = {
        'created': {
            'initialize': {'dest': 'initialized'},
            'close': {'dest': 'closed'},
        },
        'initialized': {
            'run': {'dest': 'running'},
            'reset': {'dest': 'initialized', 'before': 'on_reset'},
            'close': {'dest': 'closed'},
        },
        'running': {
            'finish': {'dest': 'finished'},
            'close': {'dest': 'closed', 'before': 'on_close_while_running'},
        },
        'finished': {
            'reset': {'dest': 'initialized', 'before': 'on_reset'},
            'close': {'dest': 'closed'},
        },
    }

    all_triggers = list({trigger for v in state_map.values() for trigger in v.keys()})

    state_map_reduced = {
        state: {trigger: v2 for trigger, v2 in v.items() if trigger != 'reset'}
        for state, v in state_map.items()
    }

    paths: List[Tuple[str, Dict[str, Any]]] = []

    state = 'created'
    while not state == 'closed' and len(paths) < max_n_paths:
        trigger_map = state_map[state]
        triggers = list(trigger_map.keys())
        trigger = draw(st.sampled_from(all_triggers))
        if trigger in trigger_map:
            paths.append((trigger, trigger_map[trigger]))
            state = trigger_map[trigger]['dest']
        else:
            paths.append((trigger, {'error': MachineError}))

    while not state == 'closed':
        trigger_map = state_map_reduced[state]
        triggers = list(trigger_map.keys())
        trigger = draw(st.sampled_from(triggers))
        paths.append((trigger, trigger_map[trigger]))
        state = trigger_map[trigger]['dest']

    return paths


@given(paths=st_paths())
async def test_transitions_hypothesis(paths: List[Tuple[str, Dict[str, Any]]]):

    machine = build_state_machine(model=Machine.self_literal)
    assert machine.is_created()

    for method, map in paths:
        if error := map.get('error'):
            with pytest.raises(error):
                await getattr(machine, method)()
            continue

        if before := map.get('before'):
            setattr(machine, before, AsyncMock())

        await getattr(machine, method)()
        dest = map['dest']
        assert getattr(machine, f'is_{dest}')()

        if before:
            assert getattr(machine, before).call_count == 1
            assert getattr(machine, before).await_count == 1
