from __future__ import annotations

from io import TextIOWrapper
from queue import Queue
from typing import Generator, Literal


class _StdOut(TextIOWrapper):
    '''To be given to Pdb as stdout.'''

    def __init__(self, cli: CmdLoopInterface_):
        self._cli = cli

    def write(self, s: str, /) -> int:
        '''Pdb prints user prompt or other messages to stdout.'''
        return self._cli.write(s)

    def flush(self):
        pass


class _StdIn(TextIOWrapper):
    '''To be given to Pdb as stdin.'''

    def __init__(self, cli: CmdLoopInterface_):
        self._cli = cli

    def readline(self):
        '''Pdb waits for user input from stdin.'''
        return self._cli.prompt()


class CmdLoopInterface_:
    '''Deliver messages between the user and Pdb during Pdb.cmdloop().

    Example:

    >>> cli = CmdLoopInterface()

    Define a client function that responds to a prompt.

    >>> def user():
    ...     for prompt in cli.prompts():
    ...         cli.issue(f'Hi, I am the user. You said: {prompt!r}')

    Run the function in a thread.

    >>> from threading import Thread
    >>> thread = Thread(target=user)
    >>> thread.start()

    Send a message to the client function.

    >>> _ = cli.write('Hello, I am Pdb.')

    Wait for a response.

    >>> response = cli.prompt()
    >>> response
    "Hi, I am the user. You said: 'Hello, I am Pdb.'"

    Stop the iteration of the "for" loop in the client function.

    >>> cli.close()

    End the thread.

    >>> thread.join()



    '''

    def __init__(self) -> None:

        # str: messages or prompts to be kept until True is received.
        # True when concatenated strings to be yielded as a prompt.
        # None when the command loop exits.
        self._queue_stdout: Queue[str | Literal[True] | None] = Queue()

        # User commands to be issued to Pdb.
        self._queue_stdin: Queue[str] = Queue()

        # To be given to Pdb as stdout and stdin.
        self.stdout = _StdOut(self)
        self.stdin = _StdIn(self)

    def prompts(self) -> Generator[str, str, None]:
        '''Yield each prompt from stdout.'''
        prompt = ''
        while (msg := self._queue_stdout.get()) is not None:
            if msg is True:
                yield prompt
                prompt = ''
                continue
            prompt += msg

    def issue(self, command: str) -> None:
        '''Respond to a prompt with a command.'''
        self._queue_stdin.put(command)

    def close(self) -> None:
        '''Have the generator self.prompts() return.'''
        self._queue_stdout.put(None)

    def write(self, s: str) -> int:
        '''Called by _StdOut.write()'''
        self._queue_stdout.put(s)
        return len(s)

    def prompt(self) -> str:
        '''Called by _StdIn.readline()'''
        self._queue_stdout.put(True)
        return self._queue_stdin.get()
