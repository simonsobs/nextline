from typing import Type

from transitions import Machine
from transitions.extensions import MachineFactory
from transitions.extensions.markup import MarkupMachine


def build_state_machine(model=None, graph=False, asyncio=True, markup=False) -> Machine:
    '''Finite state machine for the nextline states.

    State Diagram:

                 .-------------.
                 |   Created   |---.
                 '-------------'   |
                       | start()   |
                       V           |
                 .-------------.   |
            .--->| Initialized |---.
    reset() |    '-------------'   |
            |      |   | run()     |
            |------'   |           |
            |          v           |
            |    .-------------.   |
            |    |   Running   |   |
            |    '-------------'   |
            |          | finish()  |
            |          |           |
            |          V           |
            |    .-------------.   |  close()  .-------------.
            '----|  Finished   |-------------->|   Closed    |
                 '-------------'               '-------------'

    >>> class Model:
    ...     def on_enter_initialized(self):
    ...         print('enter the initialized state')
    ...
    ...     def on_exit_initialized(self):
    ...        print('exit the initialized state')
    ...
    ...     def on_reset(self):
    ...        print('resetting to the initialized state')
    ...
    ...     def on_enter_running(self):
    ...        print('enter the running state')
    ...        self.finish()
    ...
    ...     def on_exit_running(self):
    ...        print('exit the running state')
    ...
    ...     def on_enter_finished(self):
    ...        print('enter the finished state')
    ...
    ...     def on_exit_finished(self):
    ...        print('exit the finished state')
    ...
    ...     def on_enter_closed(self):
    ...        print('enter the closed state')


    >>> model = Model()
    >>> machine = build_state_machine(model=model, asyncio=False)
    >>> model.state
    'created'

    >>> _ = model.start()
    enter the initialized state

    >>> model.state
    'initialized'

    >>> _ = model.reset()
    resetting to the initialized state
    exit the initialized state
    enter the initialized state

    >>> _ = model.run()
    exit the initialized state
    enter the running state
    exit the running state
    enter the finished state

    >>> model.state
    'finished'

    >>> _ = model.close()
    exit the finished state
    enter the closed state

    >>> model.state
    'closed'

    '''

    MachineClass: Type[Machine]
    if markup:
        MachineClass = MarkupMachine
    else:
        MachineClass = MachineFactory.get_predefined(graph=graph, asyncio=asyncio)

    state_conf = {
        'name': 'nextline',
        'states': [
            'created',
            'initialized',
            'running',
            'finished',
            'closed',
        ],
        'transitions': [
            ['start', 'created', 'initialized'],
            ['run', 'initialized', 'running'],
            ['finish', 'running', 'finished'],
            ['close', ['created', 'initialized', 'finished'], 'closed'],
            {
                'trigger': 'reset',
                'source': ['initialized', 'finished'],
                'dest': 'initialized',
                'before': 'on_reset',
            },
        ],
        'initial': 'created',
        'queued': True,
        # 'ignore_invalid_triggers': True,
    }

    machine = MachineClass(model=model, **state_conf)  # type: ignore
    return machine
