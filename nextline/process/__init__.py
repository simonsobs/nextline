from __future__ import annotations

__all__ = [
    'QueueCommands',
    'QueueRegistry',
    'RunArg',
    'RunResult',
    'set_queues',
    'main',
]


from .run import run_
from .types import QueueCommands, QueueRegistry, RunArg, RunResult

_q_commands: QueueCommands | None = None
_q_registry: QueueRegistry | None = None


def set_queues(q_commands: QueueCommands, q_registry: QueueRegistry) -> None:
    '''Initializer of ProcessPoolExecutor that receives the queues.'''
    global _q_commands, _q_registry
    _q_commands = q_commands
    _q_registry = q_registry


def main(run_arg: RunArg) -> RunResult:
    '''The function to be submitted to ProcessPoolExecutor.'''
    assert _q_registry
    assert _q_commands
    return run_(run_arg, _q_commands, _q_registry)
