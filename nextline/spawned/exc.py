class NotOnTraceCall(RuntimeError):
    '''Pdb.cmdloop() was called without the hook on_trace_call() being called first.

    This error can happen when sys.settrace() is called by Pdb, which will remove
    Nextline and Pdb is directly called by the system trace.

    This can happen, for example, when the user sends the Pdb command "step" at
    the very last line of the script.
    https://github.com/simonsobs/nextline/issues/1
    '''

    pass
