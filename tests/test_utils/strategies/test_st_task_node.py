from hypothesis import given
from hypothesis import strategies as st

from nextline_test_utils.strategies import st_none_or

from .node import TaskNode
from .st_node import st_task_node, st_thread_node


@given(data=st.data())
def test_st_task_node(data: st.DataObject) -> None:
    thread = data.draw(st_none_or(st_thread_node(generate_tasks=False)))
    task = data.draw(st_task_node(thread=thread))
    assert isinstance(task, TaskNode)
    if thread is not None:
        assert task.thread is thread
    assert task in task.thread.tasks
