import contextlib
from asyncio import Event, Task, create_task, gather, get_running_loop
from string import ascii_lowercase
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nextline.utils import PubSubItem


def test_init_without_asyncio_event_loop() -> None:
    with pytest.raises(RuntimeError):
        get_running_loop()
    obj = PubSubItem[str]()
    assert obj


class StatefulTest:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._cache = self._draw(st.booleans(), label='cache_init')
        self._obj = PubSubItem[str](cache=self._cache)
        self._closed = False
        self._subscriptions = list[Task[None]]()

        # A list of item lists, e.g., [['a', 'b'], ['c', 'd']].
        # It includes at least an empty list, i.e., [[]].
        # The `put()` method appends an item to the last list.
        # The `clear()` method appends a new empty list.
        self._sent = [list[str]()]

    def assert_invariants(self) -> None:
        assert self._sent
        if self._sent[-1]:
            assert self._obj.latest() == self._sent[-1][-1]
        else:
            with pytest.raises(LookupError):
                self._obj.latest()
        assert self._obj.cache == self._cache
        assert self._obj.closed == self._closed

    async def put(self) -> None:
        item = self._draw(st.text(ascii_lowercase, min_size=0))
        if self._closed:
            with pytest.raises(RuntimeError):
                await self._obj.publish(item)
        else:
            await self._obj.publish(item)
            self._sent[-1].append(item)

    async def clear(self) -> None:
        if self._closed:
            with pytest.raises(RuntimeError):
                self._obj.clear()
        else:
            self._obj.clear()
            self._sent.append([])

    async def close(self) -> None:
        await self._obj.aclose()
        self._closed = True

    async def subscribe(self) -> None:
        started = Event()
        self._subscriptions.append(create_task(self._subscription(started)))
        await started.wait()

    async def _subscription(self, started: Event) -> None:
        started.set()

        last = self._draw(st.booleans(), label='last')
        cache = self._draw(st.booleans(), label='cache_subscribe')
        received = list[str]()

        it = self._obj.subscribe(last=last, cache=cache)
        async with contextlib.aclosing(it):  # To ensure that `finally` is executed
            if self._closed:
                async for item in it:  # pragma: no cover
                    received.append(item)
                assert not received
                return

            sent = self._sent

            current_list_idx = len(sent) - 1
            current_list = sent[current_list_idx]
            current_list_size = len(current_list)

            match current_list_size, last, cache, self._cache:
                case 0, True, _, _:
                    next_item_idx = 0
                    next_item = None
                case size, True, True, True if size:
                    next_item_idx = 0
                    next_item = current_list[next_item_idx]
                case size, True, _, _ if size:
                    next_item_idx = size - 1
                    next_item = current_list[next_item_idx]
                case size, False, _, _:  # pragma: no branch
                    next_item_idx = size
                    next_item = None

            idx = 0

            if next_item is not None:
                item = await anext(it)
                assert self._obj.n_subscriptions > 0
                assert item == next_item
                received.append(item)
                idx += 1

            def flatten() -> list[str]:
                return sum(sent[current_list_idx:], list[str]())[next_item_idx:]


            async for item in it:
                assert self._obj.n_subscriptions > 0
                received.append(item)
                idx += 1
                expected = flatten()
                assert received == expected[:idx]
                break_ = self._draw(st.booleans(), label='break')
                if break_:
                    # The `finally` in `subscribe()` will be executed at `aclose()`.
                    break
            else:
                expected = flatten()
                assert received == expected

    async def __aenter__(self) -> 'StatefulTest':
        await self._obj.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self._obj.__aexit__(*args, **kwargs)
        await gather(*self._subscriptions)
        assert self._obj.n_subscriptions == 0


@settings(max_examples=500)
@given(data=st.data())
async def test_property(data: st.DataObject) -> None:
    test = StatefulTest(data)

    METHODS = [
        test.put,
        test.clear,
        test.close,
        test.subscribe,
    ]

    methods = data.draw(st.lists(st.sampled_from(METHODS)))

    test.assert_invariants()
    async with test:
        for method in methods:
            await method()
            test.assert_invariants()
