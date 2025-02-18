from typing import Optional

from hypothesis import strategies as st

from .node import TaskNode, ThreadNode


@st.composite
def st_thread_node(
    draw: st.DrawFn,
    *,
    main: Optional[bool] = None,
    generate_tasks: bool = True,
    min_tasks_size: int = 0,
    max_tasks_size: Optional[int] = None,
) -> ThreadNode:
    if main is None:
        main = draw(st.booleans())
    thread = ThreadNode(main=main, tasks=[])
    if generate_tasks:
        thread.tasks[:] = draw(
            st.lists(
                st_task_node(thread=thread),
                min_size=min_tasks_size,
                max_size=max_tasks_size,
            )
        )
    return thread


@st.composite
def st_task_node(draw: st.DrawFn, *, thread: Optional[ThreadNode] = None) -> TaskNode:
    if thread is None:
        thread = draw(st_thread_node(generate_tasks=False))
    task = TaskNode(thread=thread)
    thread.tasks.append(task)
    return task


@st.composite
def st_thread_node_list(
    draw: st.DrawFn,
    *,
    min_size: int = 1,
    max_size: Optional[int] = None,
    generate_tasks: bool = True,
) -> list[ThreadNode]:
    ret = draw(
        st.lists(
            st_thread_node(main=False, generate_tasks=generate_tasks),
            min_size=min_size,
            max_size=max_size,
        )
    )
    if ret:
        ret[0].main = True
    return ret
