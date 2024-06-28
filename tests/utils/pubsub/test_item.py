from asyncio import Event, Task, create_task, gather, get_running_loop
from collections.abc import AsyncIterator
from string import ascii_lowercase
from typing import TypeAlias

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nextline.utils import PubSubItem


def test_init_without_asyncio_event_loop() -> None:
    with pytest.raises(RuntimeError):
        get_running_loop()
    obj = PubSubItem[str]()
    assert obj


@settings(max_examples=5000)
@given(data=st.data())
async def test_property(data: st.DataObject) -> None:
    Sent: TypeAlias = list[list[str]]

    async def send() -> AsyncIterator[tuple[PubSubItem[str], Sent]]:
        ACTIONS = ['PUT', 'CLEAR', 'CLOSE']
        cache = data.draw(st.booleans(), label='cache_init')
        obj = PubSubItem[str](cache=cache)
        sent: Sent = [[]]
        assert obj.n_subscriptions == 0
        yield obj, sent
        async with obj:
            assert obj.cache == cache
            with pytest.raises(LookupError):
                obj.latest()
            closed = False
            actions = data.draw(st.lists(st.sampled_from(ACTIONS)))
            for action in actions:
                match action, closed:
                    case 'PUT', True:
                        item = data.draw(st.text(ascii_lowercase, min_size=0))
                        with pytest.raises(RuntimeError):
                            await obj.publish(item)
                    case 'PUT', False:
                        item = data.draw(st.text(ascii_lowercase, min_size=0))
                        await obj.publish(item)
                        sent[-1].append(item)
                        assert obj.latest() == item
                    case 'CLEAR', True:
                        with pytest.raises(RuntimeError):
                            obj.clear()
                        if sent and sent[-1]:
                            assert obj.latest() == sent[-1][-1]
                        else:
                            with pytest.raises(LookupError):
                                obj.latest()
                    case 'CLEAR', False:
                        obj.clear()
                        sent.append([])
                        with pytest.raises(LookupError):
                            obj.latest()
                    case 'CLOSE', _:
                        await obj.aclose()
                        closed = True
                        if sent and sent[-1]:
                            assert obj.latest() == sent[-1][-1]
                        else:
                            with pytest.raises(LookupError):
                                obj.latest()
                    case _:  # pragma: no cover
                        raise ValueError(f'Invalid: {(action, closed)!r}')
                yield obj, sent
        yield obj, sent

    async def receive(obj: PubSubItem[str], sent: Sent, event: Event) -> None:
        event.set()

        last = data.draw(st.booleans(), label='last')
        cache = data.draw(st.booleans(), label='cache_subscribe')
        it = obj.subscribe(last=last, cache=cache)

        received = list[str]()

        if obj.closed:
            async for item in it:  # pragma: no cover
                received.append(item)
            assert not received
            return

        # A list of item lists, e.g., [['a', 'b'], ['c', 'd']]
        # A new list is appended when the `clear` method is called
        # At list an empty list should be included, i.e., [[]]
        assert sent

        current_list_idx = len(sent) - 1
        current_list = sent[current_list_idx]
        current_list_size = len(current_list)

        match current_list_size, last, cache, obj.cache:
            case 0, True, _, _:
                next_item_idx = 0
                next_item = None
            case size, True, True, True if size:
                next_item_idx = 0
                next_item = current_list[next_item_idx]
            case size, True, _, _ if size:
                next_item_idx = size - 1
                next_item = current_list[next_item_idx]
            case size, False, _, _:
                next_item_idx = size
                next_item = None

        idx = 0

        if next_item is not None:
            item = await anext(it)
            assert obj.n_subscriptions > 0
            assert item == next_item
            received.append(item)
            idx += 1

        async for item in it:
            assert obj.n_subscriptions > 0
            expected = sum(sent[current_list_idx:], list[str]())[next_item_idx:]
            received.append(item)
            idx += 1
            assert received == expected[:idx]
            break_ = data.draw(st.booleans(), label='break')
            if break_:
                break
        else:
            expected = sum(sent[current_list_idx:], list[str]())[next_item_idx:]
            assert received == expected

    tasks = list[Task[None]]()

    async for obj, sent in send():
        n_new_receivers = data.draw(st.integers(0, 5), label='n_new_receivers')
        for _ in range(n_new_receivers):
            event = Event()
            tasks.append(create_task(receive(obj, sent, event)))
            await event.wait()

    await gather(*tasks)

    assert obj.n_subscriptions == 0
