from logging import getLogger
from typing import TYPE_CHECKING, Any, Optional

from nextline.plugin import Context, build_hook, log_loaded_plugins
from nextline.spawned import Command
from nextline.types import InitOptions, ResetOptions
from nextline.utils.pubsub.broker import PubSub

from .fsm import Callback, StateMachine

if TYPE_CHECKING:
    from .main import Nextline


class Imp:
    '''The interface to the finite state machine and the plugin hook.'''

    def __init__(self, nextline: 'Nextline', init_options: InitOptions) -> None:
        self._hook = build_hook()
        self.pubsub = PubSub[Any, Any]()
        self._context = Context(nextline=nextline, hook=self._hook, pubsub=self.pubsub)
        self._init_options = init_options
        self._callback = Callback(context=self._context)
        self._machine = StateMachine(callback=self._callback)
        self._logger = getLogger(__name__)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self._machine!r}>'

    def register(self, plugin: Any) -> str | None:
        return self._hook.register(plugin)

    @property
    def state(self) -> str:
        return self._machine.state

    async def run(self) -> bool:
        return await self._machine.run()

    async def wait(self) -> None:
        await self._callback.wait_for_run_finish()

    async def reset(self, reset_options: ResetOptions) -> bool:
        return await self._machine.reset(reset_options=reset_options)

    async def send_command(self, command: Command) -> None:
        await self._hook.ahook.send_command(context=self._context, command=command)

    async def interrupt(self) -> None:
        await self._hook.ahook.interrupt(context=self._context)

    async def terminate(self) -> None:
        await self._hook.ahook.terminate(context=self._context)

    async def kill(self) -> None:
        await self._hook.ahook.kill(context=self._context)

    def format_exception(self) -> Optional[str]:
        return self._hook.hook.format_exception(context=self._context)

    def result(self) -> Any:
        return self._hook.hook.result(context=self._context)

    async def aopen(self) -> None:
        self._logger.debug(f'self._init_options: {self._init_options}')
        log_loaded_plugins(hook=self._hook)
        self._hook.hook.init(context=self._context, init_options=self._init_options)
        await self._machine.aopen()

    async def aclose(self) -> None:
        await self.pubsub.close()
        await self._machine.aclose()

    async def __aenter__(self) -> 'Imp':
        await self.aopen()
        return self

    async def __aexit__(self, *_: Any, **__: Any) -> None:
        await self.aclose()
