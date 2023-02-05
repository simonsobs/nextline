from __future__ import annotations

import json
import multiprocessing as mp
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any, Optional

from tblib import pickling_support

from . import process
from .count import RunNoCounter
from .process import QueueCommands, QueueRegistry, RunArg
from .registrar import Registrar
from .types import RunNo
from .utils import MultiprocessingLogging, PubSub, RunInProcess, run_in_process

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


def _call_all(*funcs) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


@dataclass
class RunData:
    statement: str
    filename: str
    run_no: RunNo
    result: Optional[Any] = None
    exception: Optional[BaseException] = None


class Resource:
    def __init__(self) -> None:
        self.registry = PubSub[Any, Any]()
        mp_context = mp.get_context("spawn")
        self.q_commands: QueueCommands = mp_context.Queue()
        q_registry: QueueRegistry = mp_context.Queue()
        self.mp_logging = MultiprocessingLogging(mp_context=mp_context)
        initializer = partial(
            _call_all,
            self.mp_logging.initializer,
            partial(process.set_queues, self.q_commands, q_registry),
        )
        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=mp_context,
            initializer=initializer,
        )
        self.runner = partial(run_in_process, executor_factory, process.main)  # type: ignore
        self.registrar = Registrar(self.registry, q_registry)

    async def open(self):
        await self.mp_logging.open()
        await self.registrar.open()

    async def close(self):
        await self.registrar.close()
        await self.mp_logging.close()
        await self.registry.close()


class Context:
    def __init__(self, run_no_start_from: int, statement: str):
        self._resource = Resource()
        self.registry = self._resource.registry
        self.q_commands = self._resource.q_commands
        self._runner = self._resource.runner
        self._registrar = self._resource.registrar
        self._run_no_count = RunNoCounter(run_no_start_from)
        self._future: Optional[RunInProcess] = None
        self._data = RunData(
            statement=statement,
            filename=SCRIPT_FILE_NAME,
            run_no=RunNo(run_no_start_from - 1),
        )

    async def start(self):
        await self._resource.open()
        await self._registrar.script_change(
            script=self._data.statement, filename=self._data.filename
        )

    async def state_change(self, state_name: str):
        await self._registrar.state_change(state_name)

    async def shutdown(self):
        await self._resource.close()

    async def initialize(self):
        self._data.run_no = self._run_no_count()
        self._data.result = None
        self._data.exception = None
        await self._registrar.state_initialized(self._data.run_no)
        await self._registrar.run_initialized(self._data.run_no)

    async def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        if statement:
            self._data.statement = statement
            await self._registrar.script_change(
                script=statement, filename=self._data.filename
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)

    async def run(self) -> RunInProcess:
        self._future = await self._runner(
            RunArg(
                run_no=self._data.run_no,
                statement=self._data.statement,
                filename=self._data.filename,
            ),
        )
        await self._registrar.run_start()
        return self._future

    def interrupt(self) -> None:
        if self._future:
            self._future.interrupt()

    def terminate(self) -> None:
        if self._future:
            self._future.terminate()

    def kill(self) -> None:
        if self._future:
            self._future.kill()

    async def finish(self) -> None:
        assert self._future
        try:
            self._data.result, self._data.exception = await self._future
        except TypeError:
            # The process was terminated.
            pass
        finally:
            self._future = None

        if self._data.exception:
            ret = None
            fmt_exc = "".join(
                traceback.format_exception(
                    type(self._data.exception),
                    self._data.exception,
                    self._data.exception.__traceback__,
                )
            )
        else:
            ret = json.dumps(self._data.result)
            fmt_exc = None

        await self._registrar.run_end(result=ret, exception=fmt_exc)

    def result(self) -> Any:
        if exc := self._data.exception:
            # TODO: add a test for the exception
            raise exc
        return self._data.result

    def exception(self) -> Optional[BaseException]:
        return self._data.exception

    async def close(self):
        pass
