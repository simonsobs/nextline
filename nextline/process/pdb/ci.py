from __future__ import annotations

from logging import getLogger
from queue import Queue
from types import FrameType
from typing import Any, Callable, Tuple

from nextline.process.callback import Callback
from nextline.types import PromptNo, TraceNo


def pdb_command_interface(
    trace_args: Tuple[FrameType, str, Any],
    trace_no: TraceNo,
    prompt_no_counter: Callable[[], PromptNo],
    queue_stdin: Queue[str],
    queue_stdout: Queue[str | None],
    callback: Callback,
    prompt="(Pdb) ",
) -> Tuple[Callable[[], None], Callable[[str, PromptNo], None]]:

    _prompt_no: PromptNo

    def wait_prompt() -> None:
        '''Receive stdout from Pdb

        To be run in a thread during pdb._cmdloop()
        '''
        nonlocal _prompt_no
        while out := _read_until_prompt(queue_stdout, prompt):
            _prompt_no = prompt_no_counter()
            # print(_prompt_no)
            callback.prompt_start(
                trace_no=trace_no,
                prompt_no=_prompt_no,
                trace_args=trace_args,
                out=out,
            )

    def send_command(command: str, prompt_no: PromptNo) -> None:
        '''Send a command to Pdb'''
        logger = getLogger(__name__)
        logger.debug(f'send_command({command!r}, {prompt_no!r})')
        callback.prompt_end(trace_no=trace_no, prompt_no=prompt_no, command=command)
        queue_stdin.put(command)

    return wait_prompt, send_command


def _read_until_prompt(queue_stdout: Queue[str | None], prompt: str) -> str | None:
    '''Read the queue up to the prompt.

    The prompt is normally "(Pdb) ".
    '''
    out = ''
    while (m := queue_stdout.get()) is not None:
        out += m
        if prompt == m:
            break
    else:
        return None

    return out
