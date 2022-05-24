from collections import UserDict
from typing import TypeVar


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


try:
    UserDict[_KT, _VT]
except TypeError:
    # For Python 3.8
    from ._tuserdict import TUserDict as UserDict
