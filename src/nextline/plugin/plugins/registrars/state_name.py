from nextline.plugin.spec import Context, hookimpl


class StateNameRegistrar:
    @hookimpl
    async def on_change_state(self, context: Context, state_name: str) -> None:
        await context.pubsub.publish('state_name', state_name)
