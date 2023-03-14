from typing import Optional

from apluggy import PluginManager

from nextline.spec import hookimpl
from nextline.types import RunNo
from nextline.utils.pubsub.broker import PubSub

# from rich import print


class TraceNumbersRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        self._run_no = None
