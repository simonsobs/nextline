from io import TextIOWrapper
from logging import getLogger
from typing import Optional, Protocol


class PromptFuncType(Protocol):
    '''Prompt the user with text for a command.'''

    def __call__(self, text: str) -> str:
        ...


class StdInOut(TextIOWrapper):
    '''A stdin and stdout interface to prompt_func(text: str) -> str.

    Example:

    Define a prompt_func() that receives the prompt text and returns the user command.
    >>> def prompt_func(text: str) -> str:
    ...     return f'Hi, I am the user. You said: {text!r}'

    In practice, the prompt_func() would prompt the user for a command and be blocked
    until the user responds.  Here, we just return a string.

    Initialize with the prompt_func().
    >>> stdio = StdInOut(prompt_func=prompt_func)

    The `stdio` is to be given as both stdin and stdout to Pdb, or any other
    Python object that can be operated via stdout.write() and stdin.readline().

    In this example, we will call stdio.write() and stdio.readline() directly.

    Write the prompt text to stdout.
    >>> _ = stdio.write('Hello, I am Pdb. ')

    Wait for the user response.
    >>> stdio.readline()
    "Hi, I am the user. You said: 'Hello, I am Pdb. '"

    '''

    def __init__(
        self, prompt_func: PromptFuncType, prompt_end: Optional[str] = None
    ) -> None:
        # To be matched to the end of prompt text if not None.
        self.prompt_end = prompt_end

        self._prompt = prompt_func
        self._prompt_text = ''

    def write(self, s: str) -> int:
        '''Print prompt or other text.

        For example, Pdb calls this method as stdout.write(pdb.prompt).
        '''
        self._prompt_text += s
        return len(s)

    def flush(self) -> None:
        '''To replace stdout.flush()'''
        pass

    def readline(self) -> str:  # type: ignore
        '''Call the prompt_func() with the text given to write() and return the result.

        For example, Pdb calls this method as stdin.readline() for user command.
        '''

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
