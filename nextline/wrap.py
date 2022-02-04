from functools import partial

from typing import Callable
from types import CodeType


##__________________________________________________________________||
def compose(code: CodeType) -> Callable:
    """Create a function

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
    # To be given to exec() in order to address the issue
    # https://github.com/simonsobs/nextline/issues/7
    # __name__ is used in modules_to_trace in Trace.

    func = partial(exec, code, globals_)
    return func


##__________________________________________________________________||
