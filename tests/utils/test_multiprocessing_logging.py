# from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor

import pytest
from pytest import LogCaptureFixture

from nextline.utils import MultiprocessingLogging


def test_init_sync():
    '''Assert the init without the running loop.'''
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    assert MultiprocessingLogging()


async def test_multiprocessing_logging(caplog: LogCaptureFixture):
    with caplog.at_level(logging.DEBUG):
        async with MultiprocessingLogging() as mp_logging:
            with ProcessPoolExecutor(initializer=mp_logging.initializer) as executor:
                fut = executor.submit(fn)
                assert "foo" == fut.result()

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DEBUG"
    assert caplog.records[0].message == "bar"
    assert caplog.records[0].name == __name__


def fn():
    logger = logging.getLogger(__name__)
    logger.debug('bar')
    return 'foo'
