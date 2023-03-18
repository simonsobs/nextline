'''Code used in the sub-processes in which the Nextline user code is run.
'''
from __future__ import annotations

__all__ = [
    'PdbCommand',
    'Event',
    'OnEndCmdloop',
    'OnEndPrompt',
    'OnEndTrace',
    'OnEndTraceCall',
    'OnStartCmdloop',
    'OnStartPrompt',
    'OnStartTrace',
    'OnStartTraceCall',
    'OnWriteStdout',
    'QueueIn',
    'QueueOut',
    'RunArg',
    'RunResult',
    'set_queues',
    'main',
]


from .commands import PdbCommand
from .events import (
    Event,
    OnEndCmdloop,
    OnEndPrompt,
    OnEndTrace,
    OnEndTraceCall,
    OnStartCmdloop,
    OnStartPrompt,
    OnStartTrace,
    OnStartTraceCall,
    OnWriteStdout,
)
from .run import run_
from .types import QueueIn, QueueOut, RunArg, RunResult


_queue_in: QueueIn | None = None
_queue_out: QueueOut | None = None


def set_queues(queue_in: QueueIn, queue_out: QueueOut) -> None:
    '''Initializer of ProcessPoolExecutor that receives the queues.'''
    global _queue_in, _queue_out
    _queue_in = queue_in
    _queue_out = queue_out


def main(run_arg: RunArg) -> RunResult:
    '''The function to be submitted to ProcessPoolExecutor.'''
    assert _queue_in
    assert _queue_out
    return run_(run_arg, _queue_in, _queue_out)
