from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import logging
from pytest import LogCaptureFixture
from nextline.utils import MultiprocessingLogging


async def test_multiprocessing_logging(caplog: LogCaptureFixture):
    with caplog.at_level(logging.DEBUG):
        async with MultiprocessingLogging() as mp_logging:
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
