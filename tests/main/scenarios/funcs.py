from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Iterable, TypeVar

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    _T = TypeVar('_T', bound=DataclassInstance)


def replace_with_bool(obj: _T, fields: Iterable[str]) -> _T:
    changes = {f: not not getattr(obj, f) for f in fields}
    return dataclasses.replace(obj, **changes)  # type: ignore
