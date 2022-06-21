from __future__ import annotations

from functools import partial
from pdb import Pdb

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .proxy import PdbInterface


def getlines(func_org, statement, filename, module_globals=None):
    if filename == "<string>":
        return statement.split("\n")
    return func_org(filename, module_globals)


class CustomizedPdb(Pdb):
    """A Pdb subclass that calls back PdbProxy"""

    def __init__(self, pdbi: PdbInterface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pdbi = pdbi

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)  # type: ignore

    def trace_dispatch(self, frame, event, arg):
        """The main trace function of Bdb"""
        return super().trace_dispatch(frame, event, arg)

    def _cmdloop(self):
        """Prompt user input"""
        try:
            self._pdbi.entering_cmdloop()
        except RuntimeError:
            # "step" at the last line
            # https://github.com/simonsobs/nextline/issues/1
            return
        try:
            # super()._cmdloop()  # This catches KeyboardInterrupt
            super().cmdloop()
        finally:
            self._pdbi.exited_cmdloop()

    def set_continue(self):
        """override bdb.set_continue()

        To avoid sys.settrace(None) called in bdb.set_continue()

        """
        self._set_stopinfo(self.botframe, None, -1)

    # def break_here(self, frame):
    #     ret = super().break_here(frame)
    #     print('break_here', ret)
    #     return ret

    # def stop_here(self, frame):
    #     ret = super().stop_here(frame)
    #     print('stop_here', ret)
    #     return ret

    # def bp_commands(self, frame):
    #     return True

    def do_list(self, arg):
        statement = self._pdbi.statement
        import linecache

        getlines_org = linecache.getlines
        linecache.getlines = partial(getlines, getlines_org, statement)
        try:
            return super().do_list(arg)
        finally:
            linecache.getlines = getlines_org
