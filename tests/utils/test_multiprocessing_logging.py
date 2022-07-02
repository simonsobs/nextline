from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import logging
from pytest import LogCaptureFixture
from nextline.utils import (
    ProcessPoolExecutorWithLogging,
    MultiprocessingLogging,
)


def test_executor(caplog: LogCaptureFixture):
    with caplog.at_level(logging.DEBUG):
        with ProcessPoolExecutorWithLogging(1) as executor:
            fut = executor.submit(fn)
            assert "foo" == fut.result()

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DEBUG"
    assert caplog.records[0].message == "bar"
    assert caplog.records[0].name == __name__


def mock_initializer():
    logger = logging.getLogger(__name__)
    logger.info("baz")


def test_executor_initializer(caplog: LogCaptureFixture):
    with caplog.at_level(logging.DEBUG):
        with ProcessPoolExecutorWithLogging(
            1, initializer=mock_initializer
        ) as executor:
            fut = executor.submit(fn)
            assert "foo" == fut.result()

    assert len(caplog.records) == 2
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[0].message == "baz"
    assert caplog.records[0].name == __name__
    assert caplog.records[1].levelname == "DEBUG"
    assert caplog.records[1].message == "bar"
    assert caplog.records[1].name == __name__


def mock_initializer_with_args(arg1, arg2):
    logger = logging.getLogger(__name__)
    logger.info(f"{arg1} {arg2}")


def test_executor_initializer_with_args(caplog: LogCaptureFixture):
    with caplog.at_level(logging.DEBUG):
        with ProcessPoolExecutorWithLogging(
            1, initializer=mock_initializer_with_args, initargs=("qux", "quux")
        ) as executor:
            fut = executor.submit(fn)
            assert "foo" == fut.result()

    assert len(caplog.records) == 2
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[0].message == "qux quux"
    assert caplog.records[0].name == __name__
    assert caplog.records[1].levelname == "DEBUG"
    assert caplog.records[1].message == "bar"
    assert caplog.records[1].name == __name__


def test_multiprocessing_logging(caplog: LogCaptureFixture):
    with caplog.at_level(logging.DEBUG):
        with MultiprocessingLogging() as mp_logging:
            with ProcessPoolExecutor(
                1, initializer=mp_logging.init
            ) as executor:
                fut = executor.submit(fn)
                assert "foo" == fut.result()

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DEBUG"
    assert caplog.records[0].message == "bar"
    assert caplog.records[0].name == __name__


def fn():
    logger = logging.getLogger(__name__)
    logger.debug("bar")
    return "foo"
