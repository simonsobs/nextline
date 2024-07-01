from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
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


STATE_MAP = {
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
    'closed': dict[str, dict[str, str]](),
}

TRIGGERS = list({trigger for v in STATE_MAP.values() for trigger in v.keys()})


@settings(max_examples=200)
@given(triggers=st.lists(st.sampled_from(TRIGGERS)))
async def test_transitions(triggers: list[str]) -> None:
    machine = build_state_machine(model=Machine.self_literal)
    assert machine.is_created()

    for trigger in triggers:
        prev = machine.state
        if (map_ := STATE_MAP[prev].get(trigger)) is None:
            with pytest.raises(MachineError):
                await getattr(machine, trigger)()
            assert machine.state == prev
            continue

        if before := map_.get('before'):
            setattr(machine, before, AsyncMock())

        assert await getattr(machine, trigger)() is True
        dest = map_['dest']
        assert getattr(machine, f'is_{dest}')()

        if before:
            assert getattr(machine, before).call_count == 1
            assert getattr(machine, before).await_count == 1
