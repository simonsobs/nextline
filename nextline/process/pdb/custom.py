from __future__ import annotations

from contextlib import _GeneratorContextManager
from logging import getLogger
from pdb import Pdb
from typing import Callable

from nextline.process.exc import TraceNotCalled


class CustomizedPdb(Pdb):
    '''A Pdb subclass that interfaces the command loop.'''

    def __init__(
        self,
        interface_cmdloop: Callable[[], _GeneratorContextManager[None]],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._interface_cmdloop = interface_cmdloop

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
            with self._interface_cmdloop():
                super().cmdloop(intro=intro)
        except TraceNotCalled:
            logger = getLogger(__name__)
            logger.exception('')

    def set_continue(self):
        '''Override Bdb.set_continue() to avoid sys.settrace(None).'''
        # super().set_continue()
        self._set_stopinfo(self.botframe, None, -1)
