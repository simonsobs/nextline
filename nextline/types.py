from typing import Callable, Any, Optional
from types import FrameType


TraceFunc = Callable[
    [FrameType, str, Any], Optional[Callable[[FrameType, str, Any], Any]]
]
# Copied from (because not sure how to import)
# https://github.com/python/typeshed/blob/b88a6f19cdcf/stdlib/sys.pyi#L245
