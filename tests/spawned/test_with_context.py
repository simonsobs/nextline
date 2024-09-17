from types import FrameType
from typing import Any
from unittest.mock import MagicMock, Mock, call

from hypothesis import given
from hypothesis import strategies as st

from nextline.spawned.types import TraceFunction
from nextline.spawned.utils import WithContext


@given(data=st.data())
def test_one(data: st.DataObject) -> None:
    mock_trace = Mock()
    mock_context = MagicMock()

    global_trace = WithContext(trace=mock_trace, context=mock_context)

    n_frames = data.draw(st.integers(min_value=0, max_value=10))
    for _ in range(n_frames):
        mock_trace.reset_mock(return_value=True)

        frame = Mock(spec=FrameType)

        local_trace: TraceFunction | None = global_trace
        next_mock_trace = mock_trace

        assert local_trace is not None

        n_calls = data.draw(st.integers(min_value=0, max_value=10))
        for i in range(n_calls):
            event = 'line' if i else 'call'

            local_trace = assert_trace(
                data=data,
                trace=local_trace,
                args=(frame, event, None),
                mock_trace=next_mock_trace,
                mock_context=mock_context,
            )

            if local_trace is None:
                break

            next_mock_trace = next_mock_trace.return_value


def assert_trace(
    data: st.DataObject,
    trace: TraceFunction,
    args: tuple[FrameType, str, Any],
    mock_trace: Mock,
    mock_context: MagicMock,
) -> TraceFunction | None:
    stop = data.draw(st.booleans())
    if stop:
        mock_trace.return_value = None

    mock_trace.assert_not_called()
    mock_context.reset_mock()

    returned = trace(*args)

    mock_trace.assert_called_once_with(*args)
    assert mock_context.mock_calls == [
        call(*args),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]

    if stop:
        assert returned is None

    return returned
