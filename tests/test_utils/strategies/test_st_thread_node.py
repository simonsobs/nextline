from typing import Optional, TypedDict

from hypothesis import given
from hypothesis import strategies as st

from nextline_test_utils import safe_compare as sc
from nextline_test_utils.strategies import st_none_or, st_ranges

from .node import ThreadNode
from .st_node import st_thread_node


class StThreadNodeKwargs(TypedDict, total=False):
    main: Optional[bool]
    generate_tasks: bool
    min_tasks_size: int
    max_tasks_size: Optional[int]


@st.composite
def st_st_thread_node_kwargs(draw: st.DrawFn) -> StThreadNodeKwargs:
    min_min_tasks_size = 0
    max_max_tasks_size = 5
    kwargs = StThreadNodeKwargs()
    if draw(st.booleans()):
        kwargs['main'] = draw(st_none_or(st.booleans()))
    if draw(st.booleans()):
        kwargs['generate_tasks'] = draw(st.booleans())
    if kwargs.get('generate_tasks', True):
        min_, max_ = draw(
            st_ranges(
                st.integers,
                min_start=min_min_tasks_size,
                max_end=max_max_tasks_size,
            )
        )
        if min_ is not None:
            kwargs['min_tasks_size'] = min_
        if max_ is not None:
            kwargs['max_tasks_size'] = max_
    return kwargs


@given(kwargs=st_st_thread_node_kwargs())
def test_st_st_thread_node_kwargs(kwargs: StThreadNodeKwargs) -> None:
    assert sc(kwargs.get('min_tasks_size')) <= sc(kwargs.get('max_tasks_size'))


@given(data=st.data())
def test_st_thread_node(data: st.DataObject) -> None:
    kwargs = data.draw(st_st_thread_node_kwargs())
    thread = data.draw(st_thread_node(**kwargs))

    assert isinstance(thread, ThreadNode)

    if kwargs.get('main') is not None:
        assert thread.main == kwargs['main']

    if not kwargs.get('generate_tasks', True):
        assert not thread.tasks
    else:
        min_ = kwargs.get('min_tasks_size')
        max_ = kwargs.get('max_tasks_size')
        assert sc(min_) <= len(thread.tasks) <= sc(max_)

    assert all(task.thread is thread for task in thread.tasks)
