from __future__ import annotations
from collections import UserDict
from typing import (
    Generic,
    Optional,
    TypeVar,
    MutableMapping,
    KeysView,
    ValuesView,
    ItemsView,
    Protocol,
    Iterable,
    overload,
)


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")
_VT_co = TypeVar("_VT_co", covariant=True)


class SupportsKeysAndGetItem(Protocol[_KT, _VT_co]):
    def keys(self) -> Iterable[_KT]:
        ...

    def __getitem__(self, __k: _KT) -> _VT_co:
        ...


class TUserDict(UserDict, MutableMapping[_KT, _VT], Generic[_KT, _VT]):
    """Trying to make type hints on UserDict work in Python 3.8

    Copied many lines from
    https://github.com/python/typeshed/blob/master/stdlib/typing.pyi

    It should be possible to just use the typing.pyi but not clear how to do it

    """

    def __getitem__(self, key: _KT) -> _VT:
        return super().__getitem__(key)

    @overload
    def get(self, key: _KT) -> Optional[_VT]:
        ...

    @overload
    def get(self, key: _KT, default: _VT | _T) -> _VT | _T:
        ...

    def get(self, key, default=None):
        return super().get(key, default)

    def items(self) -> ItemsView[_KT, _VT]:
        return super().items()

    def keys(self) -> KeysView[_KT]:
        return super().keys()

    def values(self) -> ValuesView[_VT]:
        return super().values()

    def __contains__(self, value: object) -> bool:
        return super().__contains__(value)

    def __setitem__(self, key: _KT, value: _VT) -> None:
        return super().__setitem__(key, value)

    def __delitem__(self, key: _KT) -> None:
        return super().__delitem__(key)

    def clear(self) -> None:
        return super().clear()

    @overload
    def pop(self, key: _KT) -> _VT:
        ...

    @overload
    def pop(self, key: _KT, default: _VT | _T) -> _VT | _T:
        ...

    def pop(self, key, default=None):
        return super().pop(key, default)

    def popitem(self) -> tuple[_KT, _VT]:
        return super().popitem()

    @overload
    def setdefault(self: TUserDict[_KT, _T | None], key: _KT) -> _T | None:
        ...

    @overload
    def setdefault(self, key: _KT, default: _VT) -> _VT:
        ...

    def setdefault(self, key, default=None):
        return super().setdefault(key, default)

    @overload
    def update(
        self, __m: SupportsKeysAndGetItem[_KT, _VT], **kwargs: _VT
    ) -> None:
        ...

    @overload
    def update(self, __m: Iterable[tuple[_KT, _VT]], **kwargs: _VT) -> None:
        ...

    @overload
    def update(self, **kwargs: _VT) -> None:
        ...

    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)
