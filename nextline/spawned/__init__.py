'''Code used in the sub-processes in which the Nextline user code is run.
'''
from __future__ import annotations

__all__ = [
    'OnEndCmdloop',
    'OnEndPrompt',
    'OnEndTrace',
    'OnEndTraceCall',
    'OnStartCmdloop',
    'OnStartPrompt',
    'OnStartTrace',
    'OnStartTraceCall',
    'OnWriteStdout',
    'QueueCommands',
    'QueueRegistry',
    'QueueOut',
    'RunArg',
    'RunResult',
    'set_queues',
    'main',
]


from .run import run_
from .types import (
    OnEndCmdloop,
    OnEndPrompt,
    OnEndTrace,
    OnEndTraceCall,
    OnStartCmdloop,
    OnStartPrompt,
    OnStartTrace,
    OnStartTraceCall,
    OnWriteStdout,
    QueueCommands,
    QueueOut,
    QueueRegistry,
    RunArg,
    RunResult,
)

_q_commands: QueueCommands | None = None
_q_registry: QueueRegistry | None = None

_queue_out: QueueOut | None = None


def set_queues(
    q_commands: QueueCommands, q_registry: QueueRegistry, queue_out: QueueOut
) -> None:
    '''Initializer of ProcessPoolExecutor that receives the queues.'''
    global _q_commands, _q_registry, _queue_out
    _q_commands = q_commands
    _q_registry = q_registry
    _queue_out = queue_out


def main(run_arg: RunArg) -> RunResult:
    '''The function to be submitted to ProcessPoolExecutor.'''
    assert _q_registry
    assert _q_commands
    assert _queue_out
    return run_(run_arg, _q_commands, _q_registry, _queue_out)
