from nextline.plugin.spec import Context, hookimpl
from nextline.spawned import RunArg


class RunNoRegistrar:
    @hookimpl
    async def on_initialize_run(self, context: Context, run_arg: RunArg) -> None:
        await context.pubsub.publish('run_no', run_arg.run_no)
