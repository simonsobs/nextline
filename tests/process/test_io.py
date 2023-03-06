from __future__ import annotations

import time
from threading import Thread
from typing import Iterator, Optional, TextIO
from unittest.mock import Mock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nextline.process.io import peek_stdout_by_task_and_thread


def print_lines(lines: Iterator[str], file: Optional[TextIO] = None):
    for line in lines:
        time.sleep(0.0001)
        print(line, file=file)


@given(st.data())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_one(capsys: pytest.CaptureFixture, data: st.DataObject):
    capsys.readouterr()  # clear

    # exclude line breaks
    st_chars = st.characters(
        blacklist_categories=('Cc', 'Cs'), blacklist_characters='\r\n'
    )

    # text to be printed per thread
    st_lines = st.lists(st.text(st_chars))

    # text to be printed in each thread
    lines_list = data.draw(st.lists(st_lines, max_size=10), label='lines')

    threads = tuple(Thread(target=print_lines, args=(t,)) for t in lines_list)

    to_peek = data.draw(
        st.lists(st.sampled_from(threads) if threads else st.nothing(), unique=True)
    )

    callback = Mock()

    with peek_stdout_by_task_and_thread(to_peek=to_peek, callback=callback):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    expected = sorted(
        [
            (thread, f'{t}\n')
            for thread, ll in zip(threads, lines_list)
            for t in ll
            if thread in to_peek and ll
        ],
        key=lambda x: x[0].name,
    )

    actual = sorted([c.args for c in callback.call_args_list], key=lambda x: x[0].name)

    assert expected == actual

    capsys.readouterr()
