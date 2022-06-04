from __future__ import annotations

import dataclasses
import datetime
import traceback
import json
from weakref import WeakKeyDictionary

from typing import TYPE_CHECKING

from .utils import SubscribableDict
from .types import RunInfo

if TYPE_CHECKING:
    from .state import State

SCRIPT_FILE_NAME = "<string>"


class Registrar:
    def __init__(self, registry: SubscribableDict):
        self._registry = registry
        self._registry["run_no_map"] = WeakKeyDictionary()
        self._registry["trace_no_map"] = WeakKeyDictionary()

    def script_change(self, script: str, filename: str) -> None:
        self._registry["statement"] = script
        self._registry["script_file_name"] = filename

    def state_change(self, state: State) -> None:
        self._registry["state_name"] = state.name

    def run_start(self):
        self._run_info = RunInfo(
            run_no=self._registry["run_no"],
            state="running",
            script=self._registry["statement"],
            started_at=datetime.datetime.now(),
        )
        self._registry["run_info"] = self._run_info

    def run_end(self, result, exception) -> None:
        if exception:
            exception = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
        if not exception:
            result = json.dumps(result)
        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=result,
            exception=exception,
            ended_at=datetime.datetime.now(),
        )
        # TODO: check if run_no matches
        self._registry["run_info"] = self._run_info
