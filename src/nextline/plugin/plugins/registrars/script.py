from nextline.plugin.spec import Context, hookimpl


class ScriptRegistrar:
    @hookimpl
    async def on_change_script(
        self, context: Context, script: str, filename: str
    ) -> None:
        await context.pubsub.publish('statement', script)
        await context.pubsub.publish('script_file_name', filename)
