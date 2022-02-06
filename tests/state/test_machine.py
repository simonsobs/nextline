import asyncio

import pytest

from nextline.state import Machine

# __________________________________________________________________||
SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()


# __________________________________________________________________||
@pytest.mark.asyncio
async def test_repr():
    machine = Machine(SOURCE)
    repr(machine)


@pytest.mark.asyncio
async def test_state_transitions_single_op():

    machine = Machine(SOURCE)
    event_initialized = asyncio.Event()
    task_monitor_state = asyncio.create_task(
        monitor_state(machine, event_initialized)
    )
    await event_initialized.wait()

    machine.run()

    await machine.finish()
    await machine.close()

    aws = [task_monitor_state]
    results = await asyncio.gather(*aws)

    states, *_ = results

    expectecd = ["initialized", "running", "exited", "finished", "closed"]
    assert expectecd == states


@pytest.mark.asyncio
async def test_state_transitions_multiple_async_ops():
    """test state transitions with multiple asynchronous operations

    The methods finish() and close() can be called multiple times
    asynchronously. However, each state transition should occur once.

    """

    nclients = 3

    machine = Machine(SOURCE)

    event_initialized = asyncio.Event()
    task_monitor_state = asyncio.create_task(
        monitor_state(machine, event_initialized)
    )
    await event_initialized.wait()

    machine.run()

    tasks_finish_and_close = []
    for _ in range(nclients):
        task = asyncio.create_task(finish_and_close(machine))
        tasks_finish_and_close.append(task)

    aws = [task_monitor_state, *tasks_finish_and_close]
    results = await asyncio.gather(*aws)

    states, *_ = results

    expectecd = ["initialized", "running", "exited", "finished", "closed"]
    assert expectecd == states


async def finish_and_close(machine):
    await machine.finish()
    await machine.close()


async def monitor_state(machine, event_initialized):
    ret = []
    async for s in machine.registry.subscribe("state_name"):
        if s == "initialized":
            event_initialized.set()
        # print('monitor_state()', s)
        ret.append(s)
    return ret


# __________________________________________________________________||
@pytest.mark.asyncio
async def test_reset():
    machine = Machine(SOURCE)
    machine.run()
    await machine.finish()
    machine.reset()
    machine.run()
    await machine.finish()
    await machine.close()


@pytest.mark.asyncio
async def test_reset_with_statement():
    machine = Machine(SOURCE)
    assert SOURCE == machine.registry.get("statement")
    machine.run()
    await machine.finish()
    machine.reset(statement=SOURCE_TWO)
    assert SOURCE_TWO == machine.registry.get("statement")
    machine.run()
    await machine.finish()
    await machine.close()


# __________________________________________________________________||
