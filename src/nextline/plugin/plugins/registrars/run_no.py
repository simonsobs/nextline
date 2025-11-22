from nextline.plugin.spec import Context, hookimpl


class RunNoRegistrar:
    @hookimpl
    async def on_initialize_run(self, context: Context) -> None:
        assert context.run_arg
        await context.pubsub.publish('run_no', context.run_arg.run_no)
