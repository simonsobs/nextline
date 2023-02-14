from __future__ import annotations

from functools import partial
from logging import getLogger
from pdb import Pdb
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .proxy import PdbInterface


def getlines(func_org, statement, filename, module_globals=None):
    if filename == "<string>":
        return statement.split("\n")
    return func_org(filename, module_globals)


class CustomizedPdb(Pdb):
    '''A Pdb subclass that calls back PdbProxy'''

    def __init__(self, pdbi: PdbInterface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pdbi = pdbi

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)  # type: ignore

    def trace_dispatch(self, frame, event, arg):
        '''The main trace function of Bdb.'''
        return super().trace_dispatch(frame, event, arg)

    def _cmdloop(self) -> None:
        '''Overriding. Called when prompting user for commands.'''
        try:
            with self._pdbi.during_cmdloop():

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
        '''Override bdb.set_continue()

        To avoid sys.settrace(None) called in bdb.set_continue()

        '''
        self._set_stopinfo(self.botframe, None, -1)

    def do_list(self, arg):
        statement = self._pdbi.statement
        import linecache

        getlines_org = linecache.getlines
        linecache.getlines = partial(getlines, getlines_org, statement)
        try:
            return super().do_list(arg)
        finally:
            linecache.getlines = getlines_org
