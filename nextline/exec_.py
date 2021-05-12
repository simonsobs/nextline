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
        The callable to be called after the code exits.

    """
    trace_org = sys.gettrace()
    threading.settrace(trace)
    sys.settrace(trace)
    try:
        exec(code)
    except BaseException as e:
        print(e)
        raise
    finally:
        sys.settrace(trace_org)
        threading.settrace(trace_org)
        if done:
            done()

##__________________________________________________________________||
