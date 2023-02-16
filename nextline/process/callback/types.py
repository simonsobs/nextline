from __future__ import annotations

from asyncio import Task
from threading import Thread
from types import FrameType
from typing import Any, MutableMapping, Tuple

from typing_extensions import TypeAlias

from nextline.types import TraceNo

TraceArgs: TypeAlias = Tuple[FrameType, str, Any]
TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, TraceNo]"
