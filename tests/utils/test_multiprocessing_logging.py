import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import pytest
from pytest import LogCaptureFixture

from nextline.utils import MultiprocessingLogging


@pytest.mark.parametrize('mp_method', [None, 'spawn', 'fork', 'forkserver'])
async def test_multiprocessing_logging(
    mp_method: str | None, caplog: LogCaptureFixture
):
    mp_context = mp.get_context(mp_method) if mp_method else None

    with caplog.at_level(logging.DEBUG):
        async with MultiprocessingLogging(mp_context=mp_context) as initializer:
            with ProcessPoolExecutor(
                mp_context=mp_context, initializer=initializer
            ) as executor:
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
