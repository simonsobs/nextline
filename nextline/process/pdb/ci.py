from __future__ import annotations

from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Any, Generator, Tuple

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
    prompt_end: str,  # i.e. '(Pdb) '
):

    prompt_no_counter = context['prompt_no_counter']
    callback = context['callback']
    ci_map = context['pdb_ci_map']

    queue: Queue[str] = Queue()

    _prompt_no: PromptNo
    logger = getLogger(__name__)

    class CmdLoopInterface:
        def __init__(
            self,
            queue_stdin: Queue[str],
            queue_stdout: Queue[str | None],
            prompt_end: str,  # i.e. '(Pdb) '
        ):
            self._queue_stdin = queue_stdin
            self._queue_stdout = queue_stdout
            self._prompt_end = prompt_end

        def prompts(self) -> Generator[str, str, None]:
            '''Yield each Pdb prompt from stdout.'''
            prompt = ''
            while (msg := self._queue_stdout.get()) is not None:
                prompt += msg
                if self._prompt_end == msg:  # '(Pdb) '
                    yield prompt
                    prompt = ''

        def issue(self, command: str) -> None:
            self._queue_stdin.put(command)

        def close(self) -> None:
            self._queue_stdout.put(None)

    _cmdloop_interface = CmdLoopInterface(
        queue_stdin=queue_stdin, queue_stdout=queue_stdout, prompt_end=prompt_end
    )

    def _std_stream() -> Generator[str, str, None]:
        '''Return the stdout from Pdb up to the prompt.

        The prompt is normally "(Pdb) ".
        '''
        for prompt in _cmdloop_interface.prompts():
            command = yield prompt
            _cmdloop_interface.issue(command)
            yield ''

    def wait_prompt() -> None:
        '''Receive stdout from Pdb

        To be run in a thread during pdb._cmdloop()
        '''
        nonlocal _prompt_no
        for out in (c := _std_stream()):
            logger.debug(f'Pdb stdout: {out!r}')

            _prompt_no = prompt_no_counter()
            logger.debug(f'PromptNo: {_prompt_no}')

            with (
                p := callback.prompt(
                    trace_no=trace_no,
                    prompt_no=_prompt_no,
                    trace_args=trace_args,
                    out=out,
                )
            ):
                command = queue.get()
                c.send(command)
                p.gen.send(command)

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
        _cmdloop_interface.close()
        fut.result()
