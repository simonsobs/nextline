'''The configuration of the finite state machine of the nextline states.

The package "transitions" is used: https://github.com/pytransitions/transitions

State Diagram:

             .-------------.
             |   Created   |---.
             '-------------'   |
      initialize() |           |
                   |           |
                   V           |
             .-------------.   |
        .--->| Initialized |---.
reset() |    '-------------'   |
        |      |   | run()     |
        |------'   |           |
        |          v           |
        |    .-------------.   |
        |    |   Running   |---.
        |    '-------------'   |
        |          | finish()  |
        |          |           |
        |          V           |
        |    .-------------.   |  close()  .-------------.
        '----|  Finished   |-------------->|   Closed    |
             '-------------'               '-------------'

Example:

Define a model class with callbacks:

>>> class Model:
...     def on_enter_initialized(self, event):
...         print('enter the initialized state')
...
...     def on_exit_initialized(self, event):
...        print('exit the initialized state')
...
...     def on_reset(self, event):
...        print('resetting to the initialized state')
...        print(f'passed arguments: {event.args} {event.kwargs}')
...
...     def on_enter_running(self, event):
...        print('enter the running state')
...        self.finish()
...
...     def on_exit_running(self, event):
...        print('exit the running state')
...
...     def on_enter_finished(self, event):
...        print('enter the finished state')
...
...     def on_exit_finished(self, event):
...        print('exit the finished state')
...
...     def on_enter_closed(self, event):
...        print('enter the closed state')

Create a state machine with a model:

>>> from transitions import Machine

>>> model = Model()
>>> machine = Machine(model, **CONFIG)

The model is in the "created" state.

>>> model.state
'created'

The method "initialize" triggers a transition.

>>> _ = model.initialize()
enter the initialized state

A callback is called and the state is now "initialized".

>>> model.state
'initialized'

Arguments to trigger methods are passed to callbacks.

>>> _ = model.reset(10, foo='bar')
resetting to the initialized state
passed arguments: (10,) {'foo': 'bar'}
exit the initialized state
enter the initialized state

A trigger method can be called from a callback.

>>> _ = model.run()
exit the initialized state
enter the running state
exit the running state
enter the finished state

Now the model is in the "finished" state.

>>> model.state
'finished'

Let's close the model.

>>> _ = model.close()
exit the finished state
enter the closed state

>>> model.state
'closed'

'''


CONFIG = {
    'name': 'nextline',
    'states': [
        'created',
        'initialized',
        'running',
        'finished',
        'closed',
    ],
    'transitions': [
        ['initialize', 'created', 'initialized'],
        ['run', 'initialized', 'running'],
        ['finish', 'running', 'finished'],
        ['close', ['created', 'initialized', 'finished'], 'closed'],
        {
            'trigger': 'close',
            'source': ['running'],
            'dest': 'closed',
            'before': 'on_close_while_running',
        },
        {
            'trigger': 'reset',
            'source': ['initialized', 'finished'],
            'dest': 'initialized',
            'before': 'on_reset',
        },
    ],
    'initial': 'created',
    # 'queued': True,
    'send_event': True,
    # 'ignore_invalid_triggers': True,
}
