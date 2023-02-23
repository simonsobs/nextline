from __future__ import annotations

from io import TextIOWrapper
from logging import getLogger
from queue import Queue
from typing import TYPE_CHECKING, Optional, Tuple

from nextline.types import PromptNo

if TYPE_CHECKING:
    from nextline.process.run import TraceContext


class _StdOut(TextIOWrapper):
    '''To be given to Pdb as stdout.'''

    def __init__(self, cli: CmdLoopInterface):
        self._cli = cli

    def write(self, s: str, /) -> int:
        '''Pdb prints user prompt or other messages to stdout.'''
        return self._cli.write(s)

    def flush(self):
        pass


class _StdIn(TextIOWrapper):
    '''To be given to Pdb as stdin.'''

    def __init__(self, cli: CmdLoopInterface):
        self._cli = cli

    def readline(self):
        '''Pdb waits for user input from stdin.'''
        return self._cli.prompt()


class CmdLoopInterface:
    def __init__(self, context: TraceContext) -> None:

        # Must be assigned to Pdb.prompt.
        self.prompt_end: Optional[str] = None

        self._prompt_no_counter = context['prompt_no_counter']
        self._callback = context['callback']

        self._queue: Queue[Tuple[str, PromptNo]] = Queue()

        # To be given to Pdb as stdout and stdin.
        self.stdout = _StdOut(self)
        self.stdin = _StdIn(self)

        self._prompt = ''

        self._logger = getLogger(__name__)

    def write(self, s: str) -> int:
        '''Called by _StdOut.write()'''
        self._prompt += s
        return len(s)

    def prompt(self) -> str:
        '''Called by _StdIn.readline()'''
        try:
            assert self.prompt_end is not None
        except AssertionError:
            self._logger.exception('prompt() called before cmdloop()')
            raise

        self._logger.debug(f'Pdb stdout: {self._prompt!r}')

        if not self._prompt.endswith(self.prompt_end):
            self._logger.warning(
                f'{self._prompt!r} does not end with {self.prompt_end!r}'
            )

        _prompt_no = self._prompt_no_counter()
        self._logger.debug(f'PromptNo: {_prompt_no}')

        with (p := self._callback.prompt(prompt_no=_prompt_no, out=self._prompt)):

            while True:
                command, prompt_no_ = self._queue.get()
                if prompt_no_ == _prompt_no:
                    break
                self._logger.warning(f'PromptNo mismatch: {prompt_no_} != {_prompt_no}')
            p.gen.send(command)
        self._prompt = ''
        return command

    def issue(self, command: str, prompt_no: PromptNo) -> None:
        self._logger.debug(f'issue(command={command!r}, prompt_no={prompt_no!r})')
        self._queue.put((command, prompt_no))
