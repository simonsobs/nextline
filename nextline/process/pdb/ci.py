from __future__ import annotations

from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Any, Tuple

from nextline.types import PromptNo, TraceNo

if TYPE_CHECKING:
    from nextline.process.run import TraceContext


@contextmanager
def pdb_command_interface(
    trace_args: Tuple[FrameType, str, Any],
    trace_no: TraceNo,
    context: TraceContext,
    queue_stdin: Queue[str],
    queue_stdout: Queue[str | None],
    prompt: str,
):

    prompt_no_counter = context['prompt_no_counter']
    callback = context['callback']
    ci_map = context['pdb_ci_map']

    queue: Queue[str] = Queue()

    _prompt_no: PromptNo
    logger = getLogger(__name__)

    def _read_until_prompt() -> str | None:
        '''Return the stdout from Pdb up to the prompt.

        The prompt is normally "(Pdb) ".
        '''
        out = ''
        while (m := queue_stdout.get()) is not None:
            out += m
            if prompt == m:
                return out
        return None

    def wait_prompt() -> None:
        '''Receive stdout from Pdb

        To be run in a thread during pdb._cmdloop()
        '''
        nonlocal _prompt_no
        while (out := _read_until_prompt()) is not None:
            logger.debug(f'Pdb stdout: {out!r}')

            _prompt_no = prompt_no_counter()
            logger.debug(f'PromptNo: {_prompt_no}')

            callback.prompt_start(
                trace_no=trace_no,
                prompt_no=_prompt_no,
                trace_args=trace_args,
                out=out,
            )

            command = queue.get()
            callback.prompt_end(
                trace_no=trace_no, prompt_no=_prompt_no, command=command
            )
            queue_stdin.put(command)

    def end_waiting_prompt() -> None:
        queue_stdout.put(None)

    def send_command(command: str, prompt_no: PromptNo) -> None:
        '''Send a command to Pdb'''
        logger.debug(f'send_command(command={command!r}, prompt_no={prompt_no!r})')
        if prompt_no != _prompt_no:
            logger.warning(f'PromptNo mismatch: {prompt_no} != {_prompt_no}')
            return
        queue.put(command)

    fut = context['executor'].submit(wait_prompt)
    ci_map[trace_no] = send_command

    try:
        yield
    finally:
        del ci_map[trace_no]
        end_waiting_prompt()
        fut.result()
