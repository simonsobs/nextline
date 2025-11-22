from black import Mode, format_str
from hypothesis import given
from hypothesis import strategies as st

from .st_node import st_thread_node_list


@given(data=st.data())
def test_st_thread_node_list(data: st.DataObject) -> None:
    threads = data.draw(st_thread_node_list(max_size=5, generate_tasks=False))
    # ic(threads)
    lines = ['#']
    lines[len(lines) :] = ['def f1():', '    print("f1")']
    lines[len(lines) :] = ['f1()']

    script = '\n'.join(lines)
    script = format_str(script, mode=Mode())
    # ic(script)
    exec(script, globals())
