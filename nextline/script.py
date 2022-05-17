"""The creation of a callable from code to be traced.

The name of this module becomes the module name of the callable.
"""

from __future__ import annotations
from functools import partial

from typing import Callable
from types import CodeType


def compose(code: CodeType | str) -> Callable[[], None]:
    """Create a function that executes the code

    Parameters
    ----------
    code : object
        A code to be executed when the returned function is called.
        This must be an object that can be executed by the Python
        built-in Function exec().

    Returns
    -------
    function
        A function with no arguments that executes the code

    """
    globals_ = {"__name__": __name__}
    # The globals, the second arg of exec(), resolves the issue*. An
    # empty dict would suffice for the issus.
    #
    # The __name__ is given for a different purpose. It becomes the
    # module name of the returned function. The module name is used in
    # Trace.
    #
    # [*] https://github.com/simonsobs/nextline/issues/7

    func = partial(exec, code, globals_)
    return func
