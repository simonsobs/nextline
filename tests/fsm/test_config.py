from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from transitions import Machine, MachineError
from transitions.extensions import AsyncGraphMachine
from transitions.extensions.asyncio import AsyncMachine
from transitions.extensions.markup import MarkupMachine

from nextline.fsm.config import CONFIG

SELF_LITERAL = Machine.self_literal


def test_model_default() -> None:
    machine = AsyncMachine(model=None, **CONFIG)  # type: ignore
    assert not machine.models


def test_model_self_literal() -> None:
    machine = AsyncMachine(model=SELF_LITERAL, **CONFIG)  # type: ignore
    assert machine.models[0] is machine
    assert len(machine.models) == 1


def test_restore_from_markup() -> None:
    machine = MarkupMachine(model=None, **CONFIG)  # type: ignore
    assert isinstance(machine.markup, dict)
    markup = deepcopy(machine.markup)

    del markup['models']  # type: ignore

    # Add missing 'dest' for internal transitions
    for transition in markup['transitions']:
        if 'dest' not in transition:
            transition['dest'] = None

    rebuild = MarkupMachine(model=None, **markup)  # type: ignore
    assert rebuild.markup == machine.markup


@pytest.mark.skip
def test_graph(tmp_path: Path) -> None:  # pragma: no cover
    FILE_NAME = 'states.png'
    path = tmp_path / FILE_NAME
    # print(f'Saving the state diagram to {path}...')
    machine = AsyncGraphMachine(model=SELF_LITERAL, **CONFIG)  # type: ignore
    machine.get_graph().draw(path, prog='dot')


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
    'closed': {
        'close': {'dest': 'closed'},
    },
}

TRIGGERS = list({trigger for v in STATE_MAP.values() for trigger in v.keys()})


@settings(max_examples=200)
@given(triggers=st.lists(st.sampled_from(TRIGGERS)))
async def test_transitions(triggers: list[str]) -> None:
    machine = AsyncMachine(model=SELF_LITERAL, **CONFIG)  # type: ignore
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

    # TODO: Test internal transitions
