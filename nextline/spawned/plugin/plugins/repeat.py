import datetime
from collections.abc import Generator, Iterator

from apluggy import PluginManager, contextmanager

from nextline.events import (
    OnEndCmdloop,
    OnEndPrompt,
    OnEndTrace,
    OnEndTraceCall,
    OnStartCmdloop,
    OnStartPrompt,
    OnStartTrace,
    OnStartTraceCall,
    OnWriteStdout,
)
from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import QueueOut, RunArg, TraceCallInfo
from nextline.types import PromptNo, TraceNo


class Repeater:
    @hookimpl
    def init(self, hook: PluginManager, run_arg: RunArg, queue_out: QueueOut) -> None:
        self._hook = hook
        self._run_no = run_arg.run_no
        self._queue_out = queue_out

    @hookimpl
    def on_start_trace(self, trace_no: TraceNo) -> None:
        assert trace_no == self._hook.hook.current_trace_no()
        started_at = datetime.datetime.utcnow()
        thread_no = self._hook.hook.current_thread_no()
        task_no = self._hook.hook.current_task_no()
        event = OnStartTrace(
            run_no=self._run_no,
            started_at=started_at,
            trace_no=trace_no,
            thread_no=thread_no,
            task_no=task_no,
        )
        self._queue_out.put(event)

    @hookimpl
    def on_end_trace(self, trace_no: TraceNo) -> None:
        ended_at = datetime.datetime.utcnow()
        event = OnEndTrace(ended_at=ended_at, run_no=self._run_no, trace_no=trace_no)
        self._queue_out.put(event)

    @hookimpl
    @contextmanager
    def on_trace_call(self, trace_call_info: TraceCallInfo) -> Iterator[None]:
        started_at = datetime.datetime.utcnow()
        trace_no = self._hook.hook.current_trace_no()
        event_start = OnStartTraceCall(
            started_at=started_at,
            run_no=self._run_no,
            trace_no=trace_no,
            file_name=trace_call_info.file_name,
            line_no=trace_call_info.line_no,
            frame_object_id=trace_call_info.frame_object_id,
            event=trace_call_info.event,
        )
        self._queue_out.put(event_start)

        try:
            yield
        finally:
            ended_at = datetime.datetime.utcnow()
            event_end = OnEndTraceCall(
                ended_at=ended_at, run_no=self._run_no, trace_no=trace_no
            )
            self._queue_out.put(event_end)

    @hookimpl
    @contextmanager
    def on_cmdloop(self) -> Generator[None, None, None]:
        started_at = datetime.datetime.utcnow()
        trace_no = self._hook.hook.current_trace_no()
        event_start = OnStartCmdloop(
            started_at=started_at, run_no=self._run_no, trace_no=trace_no
        )
        self._queue_out.put(event_start)

        try:
            yield
        finally:
            ended_at = datetime.datetime.utcnow()
            event_end = OnEndCmdloop(
                ended_at=ended_at, run_no=self._run_no, trace_no=trace_no
            )
            self._queue_out.put(event_end)

    @hookimpl
    @contextmanager
    def on_prompt(self, prompt_no: PromptNo, text: str) -> Generator[None, str, None]:
        started_at = datetime.datetime.utcnow()
        trace_no: TraceNo = self._hook.hook.current_trace_no()
        trace_call_info: TraceCallInfo = self._hook.hook.current_trace_call_info()
        event_start = OnStartPrompt(
            started_at=started_at,
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            prompt_text=text,
            file_name=trace_call_info.file_name,
            line_no=trace_call_info.line_no,
            frame_object_id=trace_call_info.frame_object_id,
            event=trace_call_info.event,
        )
        self._queue_out.put(event_start)

        command = ''

        try:
            command = yield
            yield
        finally:
            ended_at = datetime.datetime.utcnow()
            event_end = OnEndPrompt(
                ended_at=ended_at,
                run_no=self._run_no,
                trace_no=trace_no,
                prompt_no=prompt_no,
                command=command,
            )
            self._queue_out.put(event_end)

    @hookimpl
    def on_write_stdout(self, trace_no: TraceNo, line: str) -> None:
        written_at = datetime.datetime.utcnow()
        trace_no = self._hook.hook.current_trace_no()
        event = OnWriteStdout(
            written_at=written_at,
            run_no=self._run_no,
            trace_no=trace_no,
            text=line,
        )
        self._queue_out.put(event)
