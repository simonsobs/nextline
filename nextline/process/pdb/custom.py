from __future__ import annotations

from logging import getLogger
from pdb import Pdb
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .proxy import PdbInterface


class CustomizedPdb(Pdb):
    '''A Pdb subclass that calls back PdbProxy'''

    def __init__(self, pdbi: PdbInterface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pdbi = pdbi

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)  # type: ignore

    def _cmdloop(self) -> None:
        '''Override Pdb._cmdloop().

        Send command prompts to the user and commands to Pdb during the command loop.
        '''
        try:
            with self._pdbi.interface_cmdloop():

                # Not calling the overridden method because it catches
                # KeyboardInterrupt while calling self.cmdloop().
                # super()._cmdloop()

                # Instead directly call self.cmdloop() so to let
                # KeyboardInterrupt be raised.
                self.cmdloop()

        except self._pdbi.TraceNotCalled:
            # This error can happen when the user sends the Pdb command "step"
            # at the very last line of the script.
            # https://github.com/simonsobs/nextline/issues/1
            logger = getLogger(__name__)
            logger.exception('')

    def set_continue(self):
        '''Override Bdb.set_continue() to avoid sys.settrace(None).'''
        # super().set_continue()
        self._set_stopinfo(self.botframe, None, -1)
