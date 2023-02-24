from __future__ import annotations

from io import TextIOWrapper
from logging import getLogger
from typing import Optional, Protocol


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


class PromptFunc(Protocol):
    def __call__(self, text: str) -> str:
        ...


class CmdLoopInterface:
    def __init__(self, prompt_func: PromptFunc) -> None:

        # Must be assigned to Pdb.prompt.
        self.prompt_end: Optional[str] = None

        # To be given to Pdb as stdout and stdin.
        self.stdout = _StdOut(self)
        self.stdin = _StdIn(self)

        self._prompt = prompt_func
        self._prompt_text = ''

    def write(self, s: str) -> int:
        '''Called by _StdOut.write()'''
        self._prompt_text += s
        return len(s)

    def prompt(self) -> str:
        '''Called by _StdIn.readline()'''

        logger = getLogger(__name__)

        logger.debug(f'Prompt text: {self._prompt_text!r}')

        try:
            assert self.prompt_end is not None
        except AssertionError:
            logger.exception(f'{self.__class__.__name__!r} has no prompt_end')
            raise

        if not self._prompt_text.endswith(self.prompt_end):
            msg = f'{self._prompt_text!r} does not end with {self.prompt_end!r}'
            logger.warning(msg)

        command = self._prompt(text=self._prompt_text)

        self._prompt_text = ''

        return command
