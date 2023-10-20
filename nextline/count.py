from itertools import count
from typing import Callable, Type, TypeVar

from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceNo

_T = TypeVar("_T", bound=int)


def RunNoCounter(start: int = 1) -> Callable[[], RunNo]:
    return CastedCounter(count(start).__next__, RunNo)


def TraceNoCounter(start: int = 1) -> Callable[[], TraceNo]:
    return CastedCounter(count(start).__next__, TraceNo)


def ThreadNoCounter(start: int = 1) -> Callable[[], ThreadNo]:
    return CastedCounter(count(start).__next__, ThreadNo)


def TaskNoCounter(start: int = 1) -> Callable[[], TaskNo]:
    return CastedCounter(count(start).__next__, TaskNo)


def PromptNoCounter(start: int = 1) -> Callable[[], PromptNo]:
    return CastedCounter(count(start).__next__, PromptNo)


def CastedCounter(src: Callable[[], int], type_: Type[_T]) -> Callable[[], _T]:
    def casted_counter() -> _T:
        return type_(src())

    return casted_counter
