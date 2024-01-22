from logging import getLogger

from nextline import spawned
from nextline.plugin.spec import Context, hookimpl


class OnEvent:
    @hookimpl
    async def on_event_in_process(self, context: Context, event: spawned.Event) -> None:
        ahook = context.hook.ahook
        match event:
            case spawned.OnStartTrace():
                await ahook.on_start_trace(context=context, event=event)
            case spawned.OnEndTrace():
                await ahook.on_end_trace(context=context, event=event)
            case spawned.OnStartTraceCall():
                await ahook.on_start_trace_call(context=context, event=event)
            case spawned.OnEndTraceCall():
                await ahook.on_end_trace_call(context=context, event=event)
            case spawned.OnStartCmdloop():
                await ahook.on_start_cmdloop(context=context, event=event)
            case spawned.OnEndCmdloop():
                await ahook.on_end_cmdloop(context=context, event=event)
            case spawned.OnStartPrompt():
                await ahook.on_start_prompt(context=context, event=event)
            case spawned.OnEndPrompt():
                await ahook.on_end_prompt(context=context, event=event)
            case spawned.OnWriteStdout():
                await ahook.on_write_stdout(context=context, event=event)
            case _:
                logger = getLogger(__name__)
                logger.warning(f'Unknown event: {event!r}')
