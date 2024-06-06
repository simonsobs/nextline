from itertools import count
from typing import Callable, Type, TypeVar

from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceCallNo, TraceNo

_T = TypeVar('_T', bound=int)


def RunNoCounter(start: int = 1) -> Callable[[], RunNo]:
    '''Return a function that returns a new `RunNo` each time it is called.

    >>> counter = RunNoCounter()
    >>> RunNo(1) == counter()
    True

    >>> RunNo(2) == counter()
    True

    You can also specify the starting number.

    >>> counter = RunNoCounter(5)
    >>> RunNo(5) == counter()
    True

    >>> RunNo(6) == counter()
    True
    '''

    return CastedCounter(count(start).__next__, RunNo)


def TraceNoCounter(start: int = 1) -> Callable[[], TraceNo]:
    '''Return a function that returns a new `TraceNo` each time it is called.

    >>> counter = TraceNoCounter()
    >>> TraceNo(1) == counter()
    True

    >>> TraceNo(2) == counter()
    True

    You can also specify the starting number.

    >>> counter = TraceNoCounter(5)
    >>> TraceNo(5) == counter()
    True

    >>> TraceNo(6) == counter()
    True
    '''
    return CastedCounter(count(start).__next__, TraceNo)


def ThreadNoCounter(start: int = 1) -> Callable[[], ThreadNo]:
    '''Return a function that returns a new `ThreadNo` each time it is called.

    >>> counter = ThreadNoCounter()
    >>> ThreadNo(1) == counter()
    True

    >>> ThreadNo(2) == counter()
    True

    You can also specify the starting number.

    >>> counter = ThreadNoCounter(5)
    >>> ThreadNo(5) == counter()
    True

    >>> ThreadNo(6) == counter()
    True
    '''
    return CastedCounter(count(start).__next__, ThreadNo)


def TaskNoCounter(start: int = 1) -> Callable[[], TaskNo]:
    '''Return a function that returns a new `TaskNo` each time it is called.

    >>> counter = TaskNoCounter()
    >>> TaskNo(1) == counter()
    True

    >>> TaskNo(2) == counter()
    True

    You can also specify the starting number.

    >>> counter = TaskNoCounter(5)
    >>> TaskNo(5) == counter()
    True

    >>> TaskNo(6) == counter()
    True
    '''
    return CastedCounter(count(start).__next__, TaskNo)


def TraceCallNoCounter(start: int = 1) -> Callable[[], TraceCallNo]:
    '''Return a function that returns a new `TraceCallNo` each time it is called.

    >>> counter = TraceCallNoCounter()
    >>> TraceCallNo(1) == counter()
    True

    >>> TraceCallNo(2) == counter()
    True

    You can also specify the starting number.

    >>> counter = TraceCallNoCounter(5)
    >>> TraceCallNo(5) == counter()
    True

    >>> TraceCallNo(6) == counter()
    True
    '''
    return CastedCounter(count(start).__next__, TraceCallNo)


def PromptNoCounter(start: int = 1) -> Callable[[], PromptNo]:
    '''Return a function that returns a new `PromptNo` each time it is called.

    >>> counter = PromptNoCounter()
    >>> PromptNo(1) == counter()
    True

    >>> PromptNo(2) == counter()
    True

    You can also specify the starting number.

    >>> counter = PromptNoCounter(5)
    >>> PromptNo(5) == counter()
    True

    >>> PromptNo(6) == counter()
    True
    '''
    return CastedCounter(count(start).__next__, PromptNo)


def CastedCounter(src: Callable[[], int], type_: Type[_T]) -> Callable[[], _T]:
    def casted_counter() -> _T:
        return type_(src())

    return casted_counter
