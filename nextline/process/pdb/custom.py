from __future__ import annotations

from logging import getLogger
from pdb import Pdb
from typing import IO, Callable, ContextManager

from nextline.process.exc import TraceNotCalled


class CustomizedPdb(Pdb):
    '''A Pdb subclass that hooks the command loop.'''

    def __init__(
        self,
        cmdloop_hook: Callable[[], ContextManager[None]],
        stdin: IO[str],
        stdout: IO[str],
    ):
        super().__init__(stdin=stdin, stdout=stdout, nosigint=True, readrc=False)
        self._cmdloop_hook = cmdloop_hook

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)  # type: ignore

    def _cmdloop(self) -> None:
        '''Override Pdb._cmdloop() to keep it from catching KeyboardInterrupt.'''
        # super()._cmdloop()
        self.cmdloop()

    def cmdloop(self, intro=None) -> None:
        '''Override Cmd.cmdloop() to call it inside a context manager.'''
        try:
            with self._cmdloop_hook():
                super().cmdloop(intro=intro)
        except TraceNotCalled:
            logger = getLogger(__name__)
            logger.exception('')

    def set_continue(self):
        '''Override Bdb.set_continue() to avoid sys.settrace(None).'''
        # super().set_continue()
        self._set_stopinfo(self.botframe, None, -1)
