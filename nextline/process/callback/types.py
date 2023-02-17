from types import FrameType
from typing import Any, Tuple

from typing_extensions import TypeAlias

TraceArgs: TypeAlias = Tuple[FrameType, str, Any]
