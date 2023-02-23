from __future__ import annotations

from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Any, Tuple

from nextline.types import PromptNo, TraceNo

from .stream import CmdLoopInterface_

if TYPE_CHECKING:
    from nextline.process.run import TraceContext


@contextmanager
def pdb_command_interface(
    trace_args: Tuple[FrameType, str, Any],
    trace_no: TraceNo,
    context: TraceContext,
    cmdloop_interface: CmdLoopInterface_,
    prompt_end: str,  # i.e. '(Pdb) '
):

    prompt_no_counter = context['prompt_no_counter']
    callback = context['callback']
    ci_map = context['pdb_ci_map']

    queue: Queue[Tuple[str, PromptNo]] = Queue()

    logger = getLogger(__name__)

    def interact() -> None:
        '''Issue a command to each prompt.

        To be run in a thread during pdb._cmdloop()
        '''
        for prompt in cmdloop_interface.prompts():
            logger.debug(f'Pdb stdout: {prompt!r}')

            if not prompt.endswith(prompt_end):
                logger.warning(f'{prompt!r} does not end with {prompt_end!r}')

            _prompt_no = prompt_no_counter()
            logger.debug(f'PromptNo: {_prompt_no}')

            with (
                p := callback.prompt(
                    trace_no=trace_no,
                    prompt_no=_prompt_no,
                    trace_args=trace_args,
                    out=prompt,
                )
            ):
                while True:
                    command, prompt_no_ = queue.get()
                    if prompt_no_ == _prompt_no:
                        break
                    logger.warning(f'PromptNo mismatch: {prompt_no_} != {_prompt_no}')
                cmdloop_interface.issue(command)
                p.gen.send(command)

    def send_command(command: str, prompt_no: PromptNo) -> None:
        '''Send a command to Pdb'''
        logger.debug(f'send_command(command={command!r}, prompt_no={prompt_no!r})')
        queue.put((command, prompt_no))

    fut = context['executor'].submit(interact)
    ci_map[trace_no] = send_command

    try:
        yield
    finally:
        del ci_map[trace_no]
        cmdloop_interface.close()
        fut.result()
