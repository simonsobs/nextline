from __future__ import annotations

import json
import multiprocessing as mp
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Optional

from tblib import pickling_support
from typing_extensions import ParamSpec

from .count import RunNoCounter
from .process import run
from .process.run import QueueCommands, QueueRegistry, RunArg
from .registrar import Registrar
from .types import RunNo
from .utils import MultiprocessingLogging, PubSub, RunInProcess, run_in_process

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"

_P = ParamSpec("_P")


def _initializer(
    init_logging: Callable[[], Any],
    initializer: Callable[_P, Any],
    *initargs: _P.args,
    **initkwargs: _P.kwargs,
) -> None:
    init_logging()
    if initializer is not None:
        initializer(*initargs, **initkwargs)


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
        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=mp_context,
            initializer=partial(
                _initializer,
                self.mp_logging.initializer,
                run.set_queues,
            ),
            initargs=(self.q_commands, q_registry),
        )
        self.runner = partial(run_in_process, executor_factory)  # type: ignore
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
        self.func = run.main
        self._resource = Resource()
        self.registry = self._resource.registry
        self.q_commands = self._resource.q_commands
        self.runner = self._resource.runner
        self.registrar = self._resource.registrar
        self.run_no_count = RunNoCounter(run_no_start_from)
        self.future: Optional[RunInProcess] = None
        self.data = RunData(
            statement=statement,
            filename=SCRIPT_FILE_NAME,
            run_no=RunNo(run_no_start_from - 1),
        )

    async def start(self):
        await self._resource.open()
        await self.registrar.script_change(
            script=self.data.statement, filename=self.data.filename
        )

    async def state_change(self, state_name: str):
        await self.registrar.state_change(state_name)

    async def shutdown(self):
        await self._resource.close()

    async def initialize(self):
        self.data.run_no = self.run_no_count()
        self.data.result = None
        self.data.exception = None
        await self.registrar.state_initialized(self.data.run_no)
        await self.registrar.run_initialized(self.data.run_no)

    async def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        if statement:
            self.data.statement = statement
            await self.registrar.script_change(
                script=statement, filename=self.data.filename
            )
        if run_no_start_from is not None:
            self.run_no_count = RunNoCounter(run_no_start_from)

    async def run(self) -> RunInProcess:
        self.future = await self.runner(
            self.func,
            RunArg(
                run_no=self.data.run_no,
                statement=self.data.statement,
                filename=self.data.filename,
            ),
        )
        await self.registrar.run_start()
        return self.future

    def interrupt(self) -> None:
        if self.future:
            self.future.interrupt()

    def terminate(self) -> None:
        if self.future:
            self.future.terminate()

    def kill(self) -> None:
        if self.future:
            self.future.kill()

    async def finish(self) -> None:
        assert self.future
        try:
            self.data.result, self.data.exception = await self.future
        except TypeError:
            # The process was terminated.
            pass
        finally:
            self.future = None

        if self.data.exception:
            ret = None
            fmt_exc = "".join(
                traceback.format_exception(
                    type(self.data.exception),
                    self.data.exception,
                    self.data.exception.__traceback__,
                )
            )
        else:
            ret = json.dumps(self.data.result)
            fmt_exc = None

        await self.registrar.run_end(result=ret, exception=fmt_exc)

    def result(self) -> Any:
        if exc := self.data.exception:
            # TODO: add a test for the exception
            raise exc
        return self.data.result

    def exception(self) -> Optional[BaseException]:
        return self.data.exception

    async def close(self):
        pass
