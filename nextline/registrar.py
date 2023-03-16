from apluggy import PluginManager

from nextline.spawned import RunResult

from .types import RunNo
from .utils import PubSub

SCRIPT_FILE_NAME = "<string>"


class Registrar:
    def __init__(self, registry: PubSub, hook: PluginManager):
        self._hook = hook
        self._registry = registry

    async def script_change(self, script: str, filename: str) -> None:
        await self._registry.publish("statement", script)
        await self._registry.publish("script_file_name", filename)
        await self._hook.ahook.on_change_script(script=script, filename=filename)

    async def state_change(self, state_name: str) -> None:
        await self._registry.publish("state_name", state_name)

    async def state_initialized(self, run_no: int) -> None:
        await self._registry.publish("run_no", run_no)

    async def run_initialized(self, run_no: RunNo) -> None:
        await self._hook.ahook.on_initialize_run(run_no=run_no)

    async def run_start(self) -> None:
        await self._hook.ahook.on_start_run()

    async def run_end(self, run_result: RunResult) -> None:
        await self._hook.ahook.on_end_run(run_result=run_result)
