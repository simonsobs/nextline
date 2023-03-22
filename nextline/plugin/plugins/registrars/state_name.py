from nextline.plugin.spec import hookimpl
from nextline.utils.pubsub.broker import PubSub


class StateNameRegistrar:
    @hookimpl
    def init(self, registry: PubSub) -> None:
        self._registry = registry

    @hookimpl
    async def on_change_state(self, state_name: str) -> None:
        await self._registry.publish('state_name', state_name)
