import asyncio
import dataclasses
from logging import getLogger

from nextline.events import (
    OnEndPrompt,
    OnEndTrace,
    OnEndTraceCall,
    OnStartPrompt,
    OnStartTrace,
    OnStartTraceCall,
)
from nextline.plugin.spec import Context, hookimpl
from nextline.types import PromptInfo, PromptNo, TraceNo


class PromptInfoRegistrar:
    def __init__(self) -> None:
        self._last_prompt_frame_map = dict[TraceNo, int]()
        self._trace_call_map = dict[TraceNo, OnStartTraceCall]()
        self._prompt_info_map = dict[PromptNo, PromptInfo]()
        self._keys = set[str]()
        self._logger = getLogger(__name__)

    @hookimpl
    async def start(self) -> None:
        self._lock = asyncio.Lock()
        pass

    @hookimpl
    async def on_initialize_run(self) -> None:
        self._last_prompt_frame_map.clear()
        self._trace_call_map.clear()
        self._prompt_info_map.clear()
        self._keys.clear()

    @hookimpl
    async def on_end_run(self, context: Context) -> None:
        async with self._lock:
            while self._keys:
                # the process might have been killed.
                key = self._keys.pop()
                await context.pubsub.end(key)

    @hookimpl
    async def on_start_trace(self, context: Context, event: OnStartTrace) -> None:
        assert context.run_arg
        trace_no = event.trace_no

        # TODO: Putting a prompt info for now because otherwise tests get stuck
        # sometimes for an unknown reason. Need to investigate
        prompt_info = PromptInfo(
            run_no=context.run_arg.run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
        )
        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await context.pubsub.publish(key, prompt_info)

    @hookimpl
    async def on_end_trace(self, context: Context, event: OnEndTrace) -> None:
        trace_no = event.trace_no
        key = f"prompt_info_{trace_no}"
        async with self._lock:
            if key in self._keys:
                self._keys.remove(key)
                await context.pubsub.end(key)

    @hookimpl
    async def on_start_trace_call(self, event: OnStartTraceCall) -> None:
        self._trace_call_map[event.trace_no] = event

    @hookimpl
    async def on_end_trace_call(self, context: Context, event: OnEndTraceCall) -> None:
        assert context.run_arg
        trace_no = event.trace_no
        trace_call = self._trace_call_map.pop(event.trace_no, None)
        if trace_call is None:
            self._logger.warning(f'No start event for {event}')
            return
        if not trace_call.frame_object_id == self._last_prompt_frame_map.get(trace_no):
            return

            # TODO: Sending a prompt info with "open=False" for now so that the
            #       arrow in the web UI moves when the Pdb is "continuing."

            # TODO: Add a test. Currently, the tests might pass without sending this
            #       prompt info.

        prompt_info = PromptInfo(
            run_no=context.run_arg.run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
            event=trace_call.event,
            file_name=trace_call.file_name,
            line_no=trace_call.line_no,
            trace_call_end=True,
        )
        await context.pubsub.publish('prompt_info', prompt_info)

        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await context.pubsub.publish(key, prompt_info)

    @hookimpl
    async def on_start_prompt(self, context: Context, event: OnStartPrompt) -> None:
        assert context.run_arg
        trace_no = event.trace_no
        prompt_no = event.prompt_no
        trace_call = self._trace_call_map[trace_no]
        prompt_info = PromptInfo(
            run_no=context.run_arg.run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            open=True,
            event=trace_call.event,
            file_name=trace_call.file_name,
            line_no=trace_call.line_no,
            stdout=event.prompt_text,
            started_at=event.started_at,
        )
        self._prompt_info_map[prompt_no] = prompt_info
        self._last_prompt_frame_map[trace_no] = trace_call.frame_object_id

        await context.pubsub.publish('prompt_info', prompt_info)

        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await context.pubsub.publish(key, prompt_info)

    @hookimpl
    async def on_end_prompt(self, context: Context, event: OnEndPrompt) -> None:
        trace_no = event.trace_no
        prompt_no = event.prompt_no
        prompt_info = self._prompt_info_map.pop(prompt_no)
        prompt_info_end = dataclasses.replace(
            prompt_info,
            open=False,
            command=event.command,
            ended_at=event.ended_at,
        )

        await context.pubsub.publish('prompt_info', prompt_info_end)

        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await context.pubsub.publish(key, prompt_info_end)
