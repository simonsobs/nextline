from logging import getLogger
from typing import Optional

from nextline.events import OnEndTraceCall, OnStartPrompt, OnStartTraceCall
from nextline.plugin.spec import Context, hookimpl
from nextline.types import PromptNotice, RunNo, TraceNo


class PromptNoticeRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_call_map = dict[TraceNo, OnStartTraceCall]()
        self._logger = getLogger(__name__)

    @hookimpl
    async def on_initialize_run(self) -> None:
        self._trace_call_map.clear()

    @hookimpl
    async def on_end_run(self, context: Context) -> None:
        await context.pubsub.end('prompt_notice')

    @hookimpl
    async def on_start_trace_call(self, event: OnStartTraceCall) -> None:
        self._trace_call_map[event.trace_no] = event

    @hookimpl
    async def on_end_trace_call(self, event: OnEndTraceCall) -> None:
        self._trace_call_map.pop(event.trace_no, None)

    @hookimpl
    async def on_start_prompt(self, context: Context, event: OnStartPrompt) -> None:
        assert context.run_arg
        trace_no = event.trace_no
        prompt_no = event.prompt_no
        trace_call = self._trace_call_map[trace_no]
        prompt_notice = PromptNotice(
            started_at=event.started_at,
            run_no=context.run_arg.run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            prompt_text=event.prompt_text,
            event=trace_call.event,
            file_name=trace_call.file_name,
            line_no=trace_call.line_no,
        )
        await context.pubsub.publish('prompt_notice', prompt_notice)
