from __future__ import annotations

__all__ = ['QueueCommands', 'QueueRegistry', 'RunArg', 'set_queues', 'main']

from typing import Any, Tuple

from .run import run_
from .types import QueueCommands, QueueRegistry, RunArg

_q_commands: QueueCommands | None = None
_q_registry: QueueRegistry | None = None


def set_queues(q_commands: QueueCommands, q_registry: QueueRegistry) -> None:
    '''Initializer of ProcessPoolExecutor that receives the queues.'''
    global _q_commands, _q_registry
    _q_commands = q_commands
    _q_registry = q_registry


def main(run_arg: RunArg) -> Tuple[Any, BaseException | None]:
    '''The function to be submitted to ProcessPoolExecutor.'''
    assert _q_registry
    assert _q_commands
    return run_(run_arg, _q_commands, _q_registry)
