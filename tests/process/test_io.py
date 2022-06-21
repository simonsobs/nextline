from __future__ import annotations

from itertools import groupby
from operator import itemgetter
import random
import string
import time
from threading import Thread
from typing import Iterator, Optional, TextIO


from nextline.process.io import peek_stdout_by_task_and_thread


from unittest.mock import Mock


def print_lines(lines: Iterator[str], file: Optional[TextIO] = None):
    for line in lines:
        time.sleep(0.0001)
        print(line, file=file)


def test_one(capsys):
    config = (
        (tuple(random_strings()), True),
        (tuple(random_strings()), True),
        (tuple(random_strings()), False),
    )
    thread_added = tuple(
        (Thread(target=print_lines, args=(c[0],)),) + c for c in config
    )
    threads = tuple(c[0] for c in thread_added)
    to_return = [c[0] for c in thread_added if c[2]]
    callback = Mock()
    with peek_stdout_by_task_and_thread(to_peek=to_return, callback=callback):
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    results = {
        k: "".join(v[1] for v in v)
        for k, v in groupby(
            sorted(
                (c.args for c in callback.call_args_list),
                key=lambda args: args[0].name,
            ),
            itemgetter(0),
        )
    }
    expected = {c[0]: "\n".join(c[1]) + "\n" for c in thread_added if c[2]}
    assert results == expected


def test_random_strings():
    lines = random_strings()
    assert all(isinstance(line, str) for line in lines)


def random_strings():
    n_lines_range = (100, 200)
    # n_lines_range = (3, 10)
    n_letters_per_line_range = (0, 300)
    # n_letters_per_line_range = (0, 5)
    # letters = string.printable
    letters = string.ascii_letters
    r = (
        "".join(
            random.choice(letters)
            for _ in range(random.randint(*n_letters_per_line_range))
        )
        for _ in range(random.randint(*n_lines_range))
    )
    return r
