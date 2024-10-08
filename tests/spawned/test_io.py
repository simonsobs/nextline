import time
from collections.abc import Iterator
from threading import Thread
from typing import Optional, TextIO
from unittest.mock import Mock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nextline.spawned.plugin.plugins.peek import peek_stdout_by_key
from nextline.utils import current_task_or_thread


def print_lines(lines: Iterator[str], file: Optional[TextIO] = None) -> None:
    for line in lines:
        time.sleep(0.0001)
        print(line, file=file)


@given(st.data())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_one(capsys: pytest.CaptureFixture, data: st.DataObject) -> None:
    capsys.readouterr()  # clear

    # exclude line breaks
    # https://hypothesis.works/articles/generating-the-right-data/
    st_chars = st.characters(blacklist_categories=['Cc', 'Cs'])

    # text to be printed per thread
    st_lines = st.lists(st.text(st_chars))

    # text to be printed in each thread
    lines_list = data.draw(st.lists(st_lines, max_size=10), label='lines')

    threads = tuple(Thread(target=print_lines, args=(t,)) for t in lines_list)

    callback = Mock()

    with peek_stdout_by_key(key_factory=current_task_or_thread, callback=callback):
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    expected = sorted(
        (
            (thread, f'{line}\n')
            for thread, lines in zip(threads, lines_list)
            for line in lines
            if lines
        ),
        key=lambda x: x[0].name,
    )

    actual = sorted((c.args for c in callback.call_args_list), key=lambda x: x[0].name)

    assert expected == actual

    capsys.readouterr()
