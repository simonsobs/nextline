import sys
import threading

##__________________________________________________________________||
def exec_with_trace(code, trace, done=None):
    """execute code with trace

    Parameters
    ----------
    code : object
        A code to be executed. This must be an object that can be
        executed by the Python built-in Function exec().
    trace: callable
        A trace function.
    done: callable, optional
        A callable with one argument. This will to be called after the
        code exits. If an exception occurs in the code, the exception
        will be given as the argument. If no exception occurs, None
        will be given.

    """
    trace_org = sys.gettrace()
    threading.settrace(trace)
    sys.settrace(trace)
    exc = None
    try:
        exec(code)
    except BaseException as e:
        exc = e
    finally:
        sys.settrace(trace_org)
        threading.settrace(trace_org)
        if done:
            done(exc)

##__________________________________________________________________||
