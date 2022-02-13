import sys
import asyncio
from threading import Thread

from dataclasses import dataclass

import inspect

import pytest
from unittest.mock import Mock

from nextline.call import call_with_trace
from nextline.trace import TraceWithCallback
from nextline.utils import UniqThreadTaskIdComposer as IdComposer

from typing import List, Set, Any, Optional
from types import FrameType

from nextline.types import TraceFunc
from nextline.utils.types import ThreadTaskId

from pprint import pprint

pytestmark = pytest.mark.skip(reason="under development")


@dataclass
class Traced:
    module: str
    func: str
    event: str
    arg: Any


def unpack_trace_call_args_list(trace: Mock) -> List[Traced]:
    return [
        Traced(
            module=c.args[0].f_globals.get("__name__"),
            func=c.args[0].f_code.co_name,
            event=c.args[1],
            arg=c.args[2],
        )
        for c in trace.call_args_list
    ]


@pytest.fixture()
def compose_id():
    """A thread task Id factory"""
    yield IdComposer()


@dataclass
class TraceCall:
    thread_task_id: ThreadTaskId
    event: str
    arg: Any
    line: int
    func: str
    module: str


class Filter:
    """A trace func that selects calls

    This trace func calls the given trace func if (1) the Id generated
    by the compose_id() is the same as the one generated in the init
    and (2) the module in which it is called is included in the given
    set of modules. If a module set is not given, the second condition
    will be be applied.
    """

    def __init__(
        self,
        compose_id: IdComposer,
        trace: TraceFunc,
        modules: Optional[Set[str]] = None,
    ):
        self.compose_id = compose_id
        self.trace = trace
        self.modules = modules
        self._id = self.compose_id()

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        id_ = self.compose_id()
        if self._id != id_:
            return
        module = frame.f_globals.get("__name__")
        if self.modules is not None:
            if module is None:
                return
            if module not in self.modules:
                return
        return self.trace(frame, event, arg)


class Probe:
    """A trace func that records calls"""

    def __init__(self, compose_id: IdComposer):
        self.compose_id = compose_id

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        trace_call = TraceCall(
            thread_task_id=self.compose_id(),
            module=frame.f_globals.get("__name__"),
            line=frame.f_lineno,
            func=frame.f_code.co_name,
            event=event,
            arg=arg,
        )
        print(trace_call)
        # task = asyncio.current_task()
        # if task:
        #     task.print_stack()
        return self


@pytest.fixture()
def probe(compose_id: IdComposer):
    """A trace func that records calls"""
    # y = Mock()
    # y.return_value = y
    y = Probe(compose_id)
    yield y


@pytest.fixture()
def returning():
    y = Mock()
    y.return_value = y
    yield y


@pytest.fixture()
def obj(probe: Probe, returning):
    """An instance of TraceWithCallback"""
    y = TraceWithCallback(wrapped=probe, returning=returning)
    yield y


def g():
    return


def func():
    # g()
    t = Thread(
        target=g,
    )
    t.start()
    t.join()
    return


def test_one(obj, probe, returning):
    call_with_trace(func, obj)
    # print()
    # pprint(unpack_trace_call_args_list(probe))
    # pprint(unpack_trace_call_args_list(returning))


async def a_create_task():
    await asyncio.create_task(asyncio.sleep(0))


async def afunc():
    x = 1
    await asyncio.sleep(0.001)  # return a future
    await asyncio.sleep(0)  # return without arg for sleep <= 0
    x = 1
    print()
    print(inspect.currentframe().f_trace)
    print(inspect.currentframe().f_back)
    print(asyncio.current_task().get_coro().cr_await)
    print()


@pytest.mark.asyncio
async def test_async(
    obj: TraceWithCallback,
    compose_id: IdComposer,
    probe: Probe,
    returning: Mock,
):
    modules = {__name__}
    modules = None
    trace = Filter(compose_id=compose_id, trace=obj, modules=modules)
    trace_org = sys.gettrace()
    sys.settrace(trace)
    await afunc()
    sys.settrace(trace_org)

    # print()
    # pprint(unpack_trace_call_args_list(probe))
    # pprint(unpack_trace_call_args_list(returning))
