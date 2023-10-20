from collections.abc import Callable, Iterator, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger
from queue import Queue
from typing import TypeVar

from apluggy import PluginManager, contextmanager

from nextline.spawned.commands import PdbCommand
from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import QueueIn
from nextline.types import PromptNo, TraceNo

QueueMap = MutableMapping[TraceNo, 'Queue[PdbCommand]']


class Prompt:
    '''A plugin that responds to the hook prompt() with commands from a queue.'''

    def __init__(self) -> None:
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager, queue_in: QueueIn) -> None:
        self._hook = hook
        self._queue_in = queue_in
        self._queue_map: QueueMap = {}

    @hookimpl
    @contextmanager
    def context(self) -> Iterator[None]:
        with relay_commands(self._queue_in, self._queue_map):
            yield

    @hookimpl
    def on_start_trace(self, trace_no: TraceNo) -> None:
        self._queue_map[trace_no] = Queue()

    @hookimpl
    def on_end_trace(self, trace_no: TraceNo) -> None:
        del self._queue_map[trace_no]

    @hookimpl
    def prompt(self, prompt_no: PromptNo) -> str:
        trace_no = self._hook.hook.current_trace_no()
        self._logger.debug(f'PromptNo: {prompt_no}')
        queue = self._queue_map[trace_no]

        while True:
            pdb_command = queue.get()
            try:
                assert pdb_command.trace_no == trace_no
            except AssertionError:
                msg = f'TraceNo mismatch: {pdb_command.trace_no} != {trace_no}'
                self._logger.exception(msg)
                raise
            if not (n := pdb_command.prompt_no) == prompt_no:
                self._logger.warning(f'PromptNo mismatch: {n} != {prompt_no}')
                continue
            return pdb_command.command


@contextmanager
def relay_commands(queue_in: QueueIn, queue_map: QueueMap) -> Iterator[None]:
    '''Pass the Pdb commands from the main process to the Pdb instances.'''
    logger = getLogger(__name__)

    def fn() -> None:
        assert queue_in
        while msg := queue_in.get():
            logger.debug(f'queue_in.get() -> {msg!r}')
            if isinstance(msg, PdbCommand):
                queue_map[msg.trace_no].put(msg)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(try_again_on_error, fn)  # type: ignore
        try:
            yield
        finally:
            queue_in.put(None)  # type: ignore
            future.result()


_T = TypeVar('_T')


def try_again_on_error(func: Callable[[], _T]) -> _T:
    '''Keep trying until the function succeeds without an exception.'''
    while True:
        try:
            return func()
        # except KeyboardInterrupt:
        #     raise
        except BaseException:
            logger = getLogger(__name__)
            logger.exception('')
