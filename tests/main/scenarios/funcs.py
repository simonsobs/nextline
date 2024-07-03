import dataclasses
from collections.abc import Iterable
from typing import TYPE_CHECKING, Optional, TypeVar

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    _T = TypeVar('_T', bound=DataclassInstance)


def replace_with_bool(obj: '_T', fields: Iterable[str]) -> '_T':
    '''Set the fields of the dataclass instance to True or False.

    This function is used to assert, for example, optional datetime fields are set.


    >>> import datetime

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


def extract_comment(line: str) -> Optional[str]:
    '''Return the comment in a line of Python code if any else None

    >>> extract_comment('func()  # step')
    '# step'

    >>> extract_comment('func()') is None
    True
    '''
    import io
    import tokenize

    comments = [
        val
        for type, val, *_ in tokenize.generate_tokens(io.StringIO(line).readline)
        if type == tokenize.COMMENT
    ]
    if comments:
        return comments[0]
    return None
