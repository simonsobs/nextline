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
) -> Tuple[Callable[[], None], Callable[[str, PromptNo], None], Callable[[], None]]:

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

    def end_waiting_prompt() -> None:
        queue_stdout.put(None)

    def send_command(command: str, prompt_no: PromptNo) -> None:
        '''Send a command to Pdb'''
        logger.debug(f'send_command(command={command!r}, prompt_no={prompt_no!r})')
        if prompt_no != _prompt_no:
            logger.warning(f'PromptNo mismatch: {prompt_no} != {_prompt_no}')
            return
        callback.prompt_end(trace_no=trace_no, prompt_no=prompt_no, command=command)
        queue_stdin.put(command)

    return wait_prompt, send_command, end_waiting_prompt
