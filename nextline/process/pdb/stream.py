from __future__ import annotations

from io import TextIOWrapper
from logging import getLogger
from typing import Optional, Protocol


class PromptFunc(Protocol):
    def __call__(self, text: str) -> str:
        ...


class CmdLoopInterface:
    '''Call the prompt_func() when stdin.readline() is called.

    Example:

    Define a prompt_func() that receives the prompt text and returns the user command.
    >>> def prompt_func(text: str) -> str:
    ...     return f'Hi, I am the user. You said: {text!r}'

    In practice, the prompt_func() would prompt the user for a command and be blocked
    until the user responds.  Here, we just return a string.

    Initialize CmdLoopInterface with the prompt_func().
    >>> cli = CmdLoopInterface(prompt_func=prompt_func)
    
    The cli.stdout and cli.stdin are to be given as stdout and stdin to Pdb, or any
    other Python object that can be operated via standard output and input streams.
    
    In this example, we will call cli.stdout.write() and cli.stdin.readline() directly.

    Write the prompt text to stdout.
    >>> _ = cli.stdout.write('Hello, I am Pdb. ')

    Wait for the user response.
    >>> cli.stdin.readline()
    "Hi, I am the user. You said: 'Hello, I am Pdb. '"

    '''

    def __init__(
        self, prompt_func: PromptFunc, prompt_end: Optional[str] = None
    ) -> None:

        # To be matched to the end of prompt text if not None.
        self.prompt_end = prompt_end

        # To be given as stdout and stdin to Pdb, for example.
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

        prompt_text = self._prompt_text

        logger = getLogger(__name__)

        logger.debug(f'Prompt text: {prompt_text!r}')

        if not self.prompt_end:
            logger.debug(f'Prompt end is not set: {self.prompt_end!r}')
        else:
            try:
                assert prompt_text.endswith(self.prompt_end)
            except AssertionError:
                msg = f'{prompt_text!r} does not end with {self.prompt_end!r}'
                logger.exception(msg)
                raise

        self._prompt_text = ''

        command = self._prompt(text=prompt_text)

        return command


class _StdOut(TextIOWrapper):
    '''To be given as stdout to Pdb, for example.'''

    def __init__(self, cli: CmdLoopInterface):
        self._cli = cli

    def write(self, s: str, /) -> int:
        '''E.g., Pdb prints user prompt or other messages to stdout.'''
        return self._cli.write(s)

    def flush(self):
        pass


class _StdIn(TextIOWrapper):
    '''To be given as stdin to Pdb, for example.'''

    def __init__(self, cli: CmdLoopInterface):
        self._cli = cli

    def readline(self):
        '''E.g., Pdb waits for user input from stdin.'''
        return self._cli.prompt()
