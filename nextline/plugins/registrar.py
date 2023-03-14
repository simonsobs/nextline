from apluggy import PluginManager
from rich import print

from nextline.spec import hookimpl


class TraceNumbersRegistrar:
    @hookimpl
    def init(self, hook: PluginManager):
        self._hook = hook
