from __future__ import annotations

import os
import signal
import asyncio
from queue import Empty

import multiprocessing as mp
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from tblib import pickling_support  # type: ignore
import logging
from logging.handlers import QueueHandler
from typing import Optional, Any

from .utils import SubscribableDict, to_thread
from .process.run import run, RunArg, QueueCommands, QueueDone, QueueLogging
from .registrar import Registrar
from .types import PromptNo, RunNo, TraceNo
from .count import RunNoCounter

_mp = mp.get_context("spawn")  # NOTE: monkey patched in tests

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


class Machine:
    """State machine

                 .-------------.
            .--->| Initialized |---.
    reset() |    '-------------'   |
            |      |   | run()     |
            |------'   |           |
            |          v           |
            |    .-------------.   |
            |    |   Running   |   |
            |    '-------------'   |
            |          | finish()  |
            |          |           |
            |          V           |
            |    .-------------.   |  close()  .-------------.
            '----|  Finished   |-------------->|   Closed    |
                 '-------------'               '-------------'


    Parameters
    ----------
    statement : str
        A Python code as a string.

    """

    def __init__(self, statement: str, run_no_start_from=1):
        filename = SCRIPT_FILE_NAME
        self.registry = SubscribableDict[Any, Any]()
        self._run_no = RunNo(run_no_start_from - 1)
        self._run_no_count = RunNoCounter(run_no_start_from)
        queue = _mp.Queue()
        self._registrar = Registrar(self.registry, queue)

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._q_logging: QueueLogging = _mp.Queue()
        self._fut_logger = self._executor.submit(
            logger_thread, self._q_logging
        )

        self.context = RunArg(
            statement=statement,
            filename=filename,
            queue=queue,
            init=ConfigureLogger(self._q_logging),
        )

        self._registrar.script_change(script=statement, filename=filename)

        self._lock_finish = asyncio.Condition()
        self._lock_close = asyncio.Condition()

        self._state: State = Initialized(self.context)
        self._state_changed()

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f"<{self.__class__.__name__} {self.state_name!r}>"

    def _state_changed(self) -> None:
        self._registrar.state_change(self._state)
        if self._state.name == "initialized":
            self._run_no = self._run_no_count()
            self.context["run_no"] = self._run_no
            self._registrar.state_initialized(self._run_no)
        elif self._state.name == "running":
            self._registrar.run_start(self._run_no)
        elif self._state.name == "finished":
            self._registrar.run_end(state=self._state)

    @property
    def state_name(self) -> str:
        """e.g., "initialized", "running","""
        try:
            return self._state.name
        except BaseException:
            return "unknown"

    def run(self) -> None:
        """Enter the running state"""
        self._state = self._state.run()
        self._state_changed()

    def send_pdb_command(
        self, command: str, prompt_no: int, trace_no: int
    ) -> None:
        self._state.send_pdb_command(
            command, PromptNo(prompt_no), TraceNo(trace_no)
        )

    def interrupt(self) -> None:
        self._state.interrupt()

    def terminate(self) -> None:
        self._state.terminate()

    async def finish(self) -> None:
        """Enter the finished state"""
        async with self._lock_finish:
            self._state = await self._state.finish()
            self._state_changed()

    def exception(self) -> Optional[Exception]:
        ret = self._state.exception()
        return ret

    def result(self) -> Any:
        return self._state.result()

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> None:
        """Enter the initialized state"""
        if statement:
            self.context["statement"] = statement
            self._registrar.script_change(
                script=statement, filename=SCRIPT_FILE_NAME
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)
            # self._registrar.reset_run_no_count(run_no_start_from)
        self._state = self._state.reset()
        self._state_changed()

    async def close(self) -> None:
        """Enter the closed state"""
        async with self._lock_close:
            self._state = self._state.close()
            self._state_changed()
            await to_thread(self._registrar.close)
            await to_thread(self.registry.close)
            self._q_logging.put(None)  # type: ignore
            await to_thread(self._fut_logger.result)
            await to_thread(self._executor.shutdown)


class StateObsoleteError(Exception):
    """Operation on an obsolete state object."""

    pass


class StateMethodError(Exception):
    """Irrelevant operation on the state."""

    pass


class ObsoleteMixin:
    def assert_not_obsolete(self):
        if self.is_obsolete():
            raise StateObsoleteError(f"The state object is obsolete: {self!r}")

    def is_obsolete(self):
        return getattr(self, "_obsolete", False)

    def obsolete(self):
        self._obsolete = True


class State(ObsoleteMixin):
    """The base state class in the Nextline state machine"""

    name = "state"

    def __repr__(self):
        # e.g., "<Initialized 'initialized'>"
        items = [self.__class__.__name__, repr(self.name)]
        if self.is_obsolete():
            items.append("obsolete")
        return f'<{" ".join(items)}>'

    def run(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def finish(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def reset(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def close(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def send_pdb_command(
        self, command: str, prompt_no: PromptNo, trace_no: TraceNo
    ) -> None:
        del command, prompt_no, trace_no
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def interrupt(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def terminate(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def exception(self) -> Optional[Exception]:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def result(self) -> Any:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")


class Initialized(State):
    """The state "initialized", ready to run

    Parameters
    ----------
    context : dict
        An instance of Context

    """

    name = "initialized"

    def __init__(self, context: RunArg):
        self._context = context

    def run(self):
        self.assert_not_obsolete()
        running = Running(self._context)
        self.obsolete()
        return running

    def reset(self):
        self.assert_not_obsolete()
        initialized = Initialized(context=self._context)
        self.obsolete()
        return initialized

    def close(self):
        self.assert_not_obsolete()
        closed = Closed()
        self.obsolete()
        return closed


class ConfigureLogger:
    def __init__(self, queue: QueueLogging):
        self._queue = queue

    def __call__(self):
        handler = QueueHandler(self._queue)
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)


class Running(State):
    """The state "running", the script is being executed.

    Parameters
    ----------
        An instance of Context
    """

    name = "running"

    def __init__(self, context: RunArg):
        self._context = context
        self._q_commands: QueueCommands = _mp.Queue()
        self._event = Event()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._fut_run = self._executor.submit(self._run)
        assert self._event.wait(2.0)

    def _run(self):
        q_done: QueueDone = _mp.Queue()

        self._p = _mp.Process(
            target=run,
            args=(self._context, self._q_commands, q_done),
            daemon=True,
        )

        self._p.start()
        self._event.set()
        self._p.join()

        try:
            return q_done.get(timeout=0.1)
        except Empty:
            return None, None  # ret, exc

    async def finish(self):
        self.assert_not_obsolete()
        ret, exc = await to_thread(self._fut_run.result)
        self._executor.shutdown()
        finished = Finished(self._context, result=ret, exception=exc)
        self.obsolete()
        return finished

    def send_pdb_command(
        self, command: str, prompt_no: PromptNo, trace_no: TraceNo
    ) -> None:
        self._q_commands.put((command, prompt_no, trace_no))

    def interrupt(self) -> None:
        if self._p.pid:
            os.kill(self._p.pid, signal.SIGINT)

    def terminate(self) -> None:
        self._p.terminate()


class Finished(State):
    """The state "finished", the script execution has finished

    The thread which executed the script has been joined.

    Parameters
    ----------
    context : dict
        An instance of Context
    result : any
        The result of the script execution, always None
    exception : exception or None
        The exception of the script execution if any. Otherwise None

    """

    name = "finished"

    def __init__(self, context: RunArg, result, exception):
        self._result = result
        self._exception = exception

        self._context = context

    def exception(self):
        """Return the exception of the script execution

        Return None if no exception has been raised.

        """
        return self._exception

    def result(self):
        """Return the result of the script execution

        None in the current implementation as the build-in function
        exec() returns None.

        Re-raise the exception if an exception has been raised in the
        script execution.

        """

        if self._exception:
            raise self._exception

        return self._result

    async def finish(self):
        # This method can be called when Nextline.finish() is
        # asynchronously called multiple times.
        self.assert_not_obsolete()
        return self

    def reset(self):
        self.assert_not_obsolete()
        initialized = Initialized(context=self._context)
        self.obsolete()
        return initialized

    def close(self):
        self.assert_not_obsolete()
        closed = Closed()
        self.obsolete()
        return closed


class Closed(State):
    """The state "closed" """

    name = "closed"

    def close(self):
        self.assert_not_obsolete()
        return self


def logger_thread(queue: QueueLogging):
    # https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
    # https://github.com/alphatwirl/mantichora/blob/v0.12.0/mantichora/hubmp.py
    while (record := queue.get()) is not None:
        logger = logging.getLogger(record.name)
        if logger.getEffectiveLevel() <= record.levelno:
            logger.handle(record)
