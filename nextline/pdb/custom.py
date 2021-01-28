from functools import partial
from pdb import Pdb

##__________________________________________________________________||
def getlines(func_org, statement, filename, module_globals=None):
    if filename == '<string>':
        return statement.split('\n')
    return func_org(filename, module_globals)

##__________________________________________________________________||
class CustomizedPdb(Pdb):
    """A customized Pdb

    An instance of this class will be created for each thread and async task

    """

    def __init__(self, proxy, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy = proxy

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)

    def _cmdloop(self):
        self.proxy.entering_cmdloop(self.curframe)
        super()._cmdloop()
        self.proxy.exited_cmdloop()

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
        statement = self.proxy.statement
        import linecache
        getlines_org = linecache.getlines
        linecache.getlines = partial(getlines, getlines_org, statement)
        try:
            return super().do_list(arg)
        finally:
            linecache.getlines = getlines_org

##__________________________________________________________________||
