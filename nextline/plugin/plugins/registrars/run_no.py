from nextline.plugin.spec import hookimpl
from nextline.spawned import RunArg
from nextline.utils.pubsub.broker import PubSub


class RunNoRegistrar:
    @hookimpl
    def init(self, registry: PubSub) -> None:
        self._registry = registry

    @hookimpl
    async def on_initialize_run(self, run_arg: RunArg) -> None:
        await self._registry.publish('run_no', run_arg.run_no)
