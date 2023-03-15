import asyncio
import dataclasses
import datetime
import time
from logging import getLogger
from typing import Dict, Optional, Set, Tuple

from apluggy import PluginManager

from nextline.spawned import (
    OnEndPrompt,
    OnEndTrace,
    OnEndTraceCall,
    OnStartPrompt,
    OnStartTrace,
    OnStartTraceCall,
    OnWriteStdout,
)
from nextline.spec import hookimpl
from nextline.types import PromptInfo, PromptNo, RunNo, StdoutInfo, TraceInfo, TraceNo
from nextline.utils.pubsub.broker import PubSub

# from rich import print


class TraceNumbersRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_nos: Tuple[TraceNo, ...] = ()

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._trace_nos = ()

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        self._run_no = None

        up_to = 0.01
        start = time.process_time()
        while self._trace_nos and time.process_time() - start < up_to:
            # on_end_trace() has not been called yet for all traces
            await asyncio.sleep(0)

        self._trace_nos = ()
        await self._registry.publish('trace_nos', self._trace_nos)

    @hookimpl
    async def on_start_trace(self, event: OnStartTrace) -> None:
        trace_no = event.trace_no
        self._trace_nos = self._trace_nos + (trace_no,)
        await self._registry.publish('trace_nos', self._trace_nos)

    @hookimpl
    async def on_end_trace(self, event: OnEndTrace) -> None:
        trace_no = event.trace_no
        nosl = list(self._trace_nos)
        try:
            nosl.remove(trace_no)
        except ValueError:
            # on_end_run() might have already been called
            return
        self._trace_nos = tuple(nosl)
        await self._registry.publish('trace_nos', self._trace_nos)


class TraceInfoRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_info_map: Dict[TraceNo, TraceInfo] = {}

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._trace_info_map = {}

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        self._run_no = None

        up_to = 0.05
        start = time.process_time()
        while self._trace_info_map and time.process_time() - start < up_to:
            # on_end_trace() has not been called yet for all traces
            await asyncio.sleep(0)

        while self._trace_info_map:
            # the process might have been killed.
            _, trace_info = self._trace_info_map.popitem()
            trace_info_end = dataclasses.replace(
                trace_info,
                state='finished',
                ended_at=datetime.datetime.utcnow(),
            )
            await self._registry.publish('trace_info', trace_info_end)

    @hookimpl
    async def on_start_trace(self, event: OnStartTrace) -> None:
        assert self._run_no is not None
        trace_info = TraceInfo(
            run_no=self._run_no,
            trace_no=event.trace_no,
            thread_no=event.thread_no,
            task_no=event.task_no,
            state='running',
            started_at=event.started_at,
        )
        self._trace_info_map[event.trace_no] = trace_info
        await self._registry.publish('trace_info', trace_info)

    @hookimpl
    async def on_end_trace(self, event: OnEndTrace) -> None:
        trace_info = self._trace_info_map.pop(event.trace_no, None)
        if trace_info is None:
            # on_end_run() might have already been called
            return
        trace_info_end = dataclasses.replace(
            trace_info,
            state='finished',
            ended_at=event.ended_at,
        )
        await self._registry.publish('trace_info', trace_info_end)


class PromptInfoRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._last_prompt_frame_map: Dict[TraceNo, int] = {}
        self._trace_call_map: Dict[TraceNo, OnStartTraceCall] = {}
        self._prompt_info_map: Dict[PromptNo, PromptInfo] = {}
        self._keys: Set[str] = set()
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def start(self) -> None:
        self._lock = asyncio.Lock()
        pass

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._last_prompt_frame_map.clear()
        self._trace_call_map.clear()
        self._prompt_info_map.clear()
        self._keys.clear()

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no

        up_to = 0.05
        start = time.process_time()
        while self._keys and time.process_time() - start < up_to:
            # on_end_trace() has not been called yet for all traces
            await asyncio.sleep(0)

        async with self._lock:
            while self._keys:
                # the process might have been killed.
                key = self._keys.pop()
                await self._registry.end(key)

        self._run_no = None

    @hookimpl
    async def on_start_trace(self, event: OnStartTrace) -> None:
        assert self._run_no is not None
        trace_no = event.trace_no

        # TODO: Putting a prompt info for now because otherwise tests get stuck
        # sometimes for an unknown reason. Need to investigate
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
        )
        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await self._registry.publish(key, prompt_info)

    @hookimpl
    async def on_end_trace(self, event: OnEndTrace) -> None:
        trace_no = event.trace_no
        key = f"prompt_info_{trace_no}"
        async with self._lock:
            if key in self._keys:
                self._keys.remove(key)
                await self._registry.end(key)

    @hookimpl
    async def on_start_trace_call(self, event: OnStartTraceCall) -> None:
        self._trace_call_map[event.trace_no] = event

    @hookimpl
    async def on_end_trace_call(self, event: OnEndTraceCall) -> None:
        assert self._run_no is not None
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
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
            event=trace_call.call_event,
            file_name=trace_call.file_name,
            line_no=trace_call.line_no,
            trace_call_end=True,
        )
        await self._registry.publish('prompt_info', prompt_info)

        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await self._registry.publish(key, prompt_info)

    @hookimpl
    async def on_start_prompt(self, event: OnStartPrompt) -> None:
        assert self._run_no is not None
        trace_no = event.trace_no
        prompt_no = event.prompt_no
        trace_call = self._trace_call_map[trace_no]
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            open=True,
            event=trace_call.call_event,
            file_name=trace_call.file_name,
            line_no=trace_call.line_no,
            stdout=event.prompt_text,
            started_at=event.started_at,
        )
        self._prompt_info_map[prompt_no] = prompt_info
        self._last_prompt_frame_map[trace_no] = trace_call.frame_object_id

        await self._registry.publish('prompt_info', prompt_info)

        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await self._registry.publish(key, prompt_info)

    @hookimpl
    async def on_end_prompt(self, event: OnEndPrompt) -> None:
        trace_no = event.trace_no
        prompt_no = event.prompt_no
        prompt_info = self._prompt_info_map.pop(prompt_no)
        prompt_info_end = dataclasses.replace(
            prompt_info,
            open=False,
            command=event.command,
            ended_at=event.ended_at,
        )

        await self._registry.publish('prompt_info', prompt_info_end)

        key = f"prompt_info_{trace_no}"
        async with self._lock:
            self._keys.add(key)
            await self._registry.publish(key, prompt_info_end)


class StdoutRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._trace_nos = ()

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        self._run_no = None

    @hookimpl
    async def on_write_stdout(self, event: OnWriteStdout) -> None:
        assert self._run_no is not None
        stdout_info = StdoutInfo(
            run_no=self._run_no,
            trace_no=event.trace_no,
            text=event.text,
            written_at=event.written_at,
        )
        await self._registry.publish('stdout', stdout_info)
