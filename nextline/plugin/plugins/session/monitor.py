from logging import getLogger

from nextline import events
from nextline.plugin.spec import Context, hookimpl


class OnEvent:
    @hookimpl
    async def on_event_in_process(self, context: Context, event: events.Event) -> None:
        ahook = context.hook.ahook
        match event:
            case events.OnStartTrace():
                await ahook.on_start_trace(context=context, event=event)
            case events.OnEndTrace():
                await ahook.on_end_trace(context=context, event=event)
            case events.OnStartTraceCall():
                await ahook.on_start_trace_call(context=context, event=event)
            case events.OnEndTraceCall():
                await ahook.on_end_trace_call(context=context, event=event)
            case events.OnStartCmdloop():
                await ahook.on_start_cmdloop(context=context, event=event)
            case events.OnEndCmdloop():
                await ahook.on_end_cmdloop(context=context, event=event)
            case events.OnStartPrompt():
                await ahook.on_start_prompt(context=context, event=event)
            case events.OnEndPrompt():
                await ahook.on_end_prompt(context=context, event=event)
            case events.OnWriteStdout():
                await ahook.on_write_stdout(context=context, event=event)
            case _:
                logger = getLogger(__name__)
                logger.warning(f'Unknown event: {event!r}')
