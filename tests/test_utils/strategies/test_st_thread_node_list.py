from typing import Optional, TypedDict

from hypothesis import given
from hypothesis import strategies as st

from nextline_test_utils import safe_compare as sc
from nextline_test_utils.strategies import st_ranges

from .st_node import st_thread_node_list


class StThreadNodeListKwargs(TypedDict, total=False):
    min_size: int
    max_size: Optional[int]
    generate_tasks: bool


@st.composite
def st_st_thread_node_list_kwargs(draw: st.DrawFn) -> StThreadNodeListKwargs:
    min_min_size = 0
    max_max_size = 5
    kwargs = StThreadNodeListKwargs()
    min_, max_ = draw(
        st_ranges(
            st.integers,
            min_start=min_min_size,
            max_end=max_max_size,
            let_end_none_if_start_none=True,
        )
    )
    if min_ is not None:
        kwargs['min_size'] = min_
    if max_ is not None:
        kwargs['max_size'] = max_
    if draw(st.booleans()):
        kwargs['generate_tasks'] = draw(st.booleans())
    return kwargs


@given(kwargs=st_st_thread_node_list_kwargs())
def test_st_st_thread_node_list_kwargs(kwargs: StThreadNodeListKwargs) -> None:
    # The minimum size should be less than or equal to the maximum size.
    assert sc(kwargs.get('min_size')) <= sc(kwargs.get('max_size'))


@given(data=st.data())
def test_st_thread_node_list(data: st.DataObject) -> None:
    kwargs = data.draw(st_st_thread_node_list_kwargs())
    threads = data.draw(st_thread_node_list(**kwargs))

    # The list length should be within the specified range.
    min_ = kwargs.get('min_size')
    max_ = kwargs.get('max_size')
    size = len(threads)
    if min_ is None:
        assert 1 <= size
    assert sc(min_) <= size <= sc(max_)

    # Only the first thread should be main.
    if threads:
        assert threads[0].main
        assert all(not thread.main for thread in threads[1:])

    # No thread should have tasks if generate_tasks is False.
    if not kwargs.get('generate_tasks', True):
        assert all(not thread.tasks for thread in threads)
