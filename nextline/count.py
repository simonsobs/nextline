from __future__ import annotations

from itertools import count
from typing import Callable, Type, TypeVar

from nextline.types import RunNo, TraceNo, ThreadNo, TaskNo, PromptNo

_T = TypeVar("_T", bound=int)


def RunNoCounter(start=1) -> Callable[[], RunNo]:
    return CastedCounter(count(start).__next__, RunNo)


def TraceNoCounter(start=1) -> Callable[[], TraceNo]:
    return CastedCounter(count(start).__next__, TraceNo)


def ThreadNoCounter(start=1) -> Callable[[], ThreadNo]:
    return CastedCounter(count(start).__next__, ThreadNo)


def TaskNoCounter(start=1) -> Callable[[], TaskNo]:
    return CastedCounter(count(start).__next__, TaskNo)


def PromptNoCounter(start=1) -> Callable[[], PromptNo]:
    return CastedCounter(count(start).__next__, PromptNo)


def CastedCounter(src: Callable[[], int], type_: Type[_T]) -> Callable[[], _T]:
    def casted_counter() -> _T:
        return type_(src())

    return casted_counter
