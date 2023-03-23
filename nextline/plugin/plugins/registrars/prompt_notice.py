from logging import getLogger
from typing import Dict, Optional

from nextline.plugin.spec import hookimpl
from nextline.spawned import OnEndTraceCall, OnStartPrompt, OnStartTraceCall, RunArg
from nextline.types import PromptNotice, RunNo, TraceNo
from nextline.utils.pubsub.broker import PubSub


class PromptNoticeRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_call_map: Dict[TraceNo, OnStartTraceCall] = {}
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, registry: PubSub) -> None:
        self._registry = registry

    @hookimpl
    async def on_initialize_run(self, run_arg: RunArg) -> None:
        self._run_no = run_arg.run_no
        self._trace_call_map.clear()

    @hookimpl
    async def on_end_run(self) -> None:
        await self._registry.end('prompt_notice')
        self._run_no = None

    @hookimpl
    async def on_start_trace_call(self, event: OnStartTraceCall) -> None:
        self._trace_call_map[event.trace_no] = event

    @hookimpl
    async def on_end_trace_call(self, event: OnEndTraceCall) -> None:
        assert self._run_no is not None
        self._trace_call_map.pop(event.trace_no, None)

    @hookimpl
    async def on_start_prompt(self, event: OnStartPrompt) -> None:
        assert self._run_no is not None
        trace_no = event.trace_no
        prompt_no = event.prompt_no
        trace_call = self._trace_call_map[trace_no]
        prompt_notice = PromptNotice(
            started_at=event.started_at,
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            prompt_text=event.prompt_text,
            event=trace_call.call_event,
            file_name=trace_call.file_name,
            line_no=trace_call.line_no,
        )
        await self._registry.publish('prompt_notice', prompt_notice)
