from logging import getLogger
from pdb import Pdb
from typing import IO, Any, Callable, ContextManager

from nextline.spawned.exc import NotOnTraceCall


class CustomizedPdb(Pdb):
    '''A Pdb subclass that hooks the command loop.'''

    def __init__(
        self,
        cmdloop_hook: Callable[[], ContextManager[None]],
        stdin: IO[str],
        stdout: IO[str],
    ):
        super().__init__(stdin=stdin, stdout=stdout, nosigint=True, readrc=False)
        # NOTE: nosigint (No SIGINT) is False by default.  When False, Pdb lets
        # the user to break into a debugger again with SIGINT after the
        # `continue` command is issued. This feature is potentially useful in
        # Nextline.
        #
        #  However, it is turned off now for two reasons:
        #
        #  1. Pdb calls `sys.settrace(None)` when the `continue` command is
        #     issued and `sys.settrace(pdb.trace_dispatch)` when SIGINT is
        #     handled, which removes Nextline.  We will need to override Pdb
        #     methods to set Nextline back.
        #
        #  2. Nextline uses multiple instances of Pdb.  We will need to break
        #     into the right instance of Pdb when SIGINT is handled.

        self._cmdloop_hook = cmdloop_hook

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)  # type: ignore

    def _cmdloop(self) -> None:
        '''Override Pdb._cmdloop() to keep it from catching KeyboardInterrupt.'''
        # super()._cmdloop()
        self.cmdloop()

    def cmdloop(self, intro: Any | None = None) -> None:
        '''Override Cmd.cmdloop() to call it inside a context manager.'''
        try:
            with self._cmdloop_hook():
                super().cmdloop(intro=intro)
        except NotOnTraceCall:
            logger = getLogger(__name__)
            logger.exception('')

    def set_continue(self) -> None:
        '''Override Bdb.set_continue() to avoid sys.settrace(None).'''
        # super().set_continue()
        self._set_stopinfo(self.botframe, None, -1)  # type: ignore
