from apluggy import PluginManager, contextmanager

from nextline.spawned.trace.spec import hookimpl
from nextline.spawned.types import OnStartTrace, QueueOut
from nextline.types import TraceNo


class Repeater:
    @hookimpl
    def init(self, queue_out: QueueOut):
        self._queue_out = queue_out

    @hookimpl
    def on_start_trace(self, trace_no: TraceNo):
        event = OnStartTrace(trace_no=trace_no)
        self._queue_out.put(event)
