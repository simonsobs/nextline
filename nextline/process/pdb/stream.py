from __future__ import annotations

from io import TextIOWrapper
from logging import getLogger
from typing import TYPE_CHECKING, Optional


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

        self._callback = context['callback']

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
            self._logger.exception(f'{self.__class__.__name__!r} has no prompt_end')
            raise

        self._logger.debug(f'Pdb stdout: {self._prompt!r}')

        if not self._prompt.endswith(self.prompt_end):
            msg = f'{self._prompt!r} does not end with {self.prompt_end!r}'
            self._logger.warning(msg)

        command = self._callback.prompt(out=self._prompt)

        self._prompt = ''
        return command
