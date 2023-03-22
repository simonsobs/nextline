from nextline.plugin.spec import hookimpl
from nextline.utils.pubsub.broker import PubSub


class ScriptRegistrar:
    @hookimpl
    def init(self, registry: PubSub) -> None:
        self._registry = registry

    @hookimpl
    async def on_change_script(self, script: str, filename: str) -> None:
        await self._registry.publish('statement', script)
        await self._registry.publish('script_file_name', filename)
