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

    def __init__(self, pdb_proxy, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pdb_proxy = pdb_proxy

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)

    def _cmdloop(self):
        self.pdb_proxy.enter_cmdloop()
        super()._cmdloop()
        self.pdb_proxy.exit_cmdloop()

    def do_list(self, arg):
        statement = self.pdb_proxy.trace.statement
        import linecache
        getlines_org = linecache.getlines
        linecache.getlines = partial(getlines, getlines_org, statement)
        try:
            return super().do_list(arg)
        finally:
            linecache.getlines = getlines_org

##__________________________________________________________________||
