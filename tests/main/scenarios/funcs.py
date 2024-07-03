import dataclasses
from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    _T = TypeVar('_T', bound=DataclassInstance)


def replace_with_bool(obj: '_T', fields: Iterable[str]) -> '_T':
    '''Set the fields of the dataclass instance to True or False.

    This function is used to assert, for example, optional datetime fields are set.


    >>> import datetime
    >>> from typing import Optional

    >>> @dataclasses.dataclass
    ... class Foo:
    ...     a: int
    ...     b: Optional[datetime.datetime] = None
    ...     c: Optional[datetime.datetime] = None
    >>> foo = Foo(1, c=datetime.datetime.now())
    >>> replace_with_bool(foo, ('b', 'c'))
    Foo(a=1, b=False, c=True)

    '''
    changes = {f: not not getattr(obj, f) for f in fields}
    return dataclasses.replace(obj, **changes)  # type: ignore
