import sys
from pathlib import Path
from types import CodeType
from typing import Any, Callable

from nextline.spawned.path import to_canonic_path
from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import RunArg

from . import _script


class CallableComposer:
    @hookimpl
    def init(self, run_arg: RunArg) -> None:
        self._run_arg = run_arg

    @hookimpl
    def compose_callable(self) -> Callable[[], Any]:
        return _compose_callable(self._run_arg)

    @hookimpl
    def clean_exception(self, exc: BaseException) -> None:
        if not isinstance(exc, SyntaxError):
            return
        is_compiled_here = False
        tb = exc.__traceback__
        while tb:
            module = tb.tb_frame.f_globals.get('__name__')
            if module == __name__:
                is_compiled_here = True
            if not tb.tb_next and is_compiled_here:
                # NOTE: tb.tb_next is None. No traceback for SyntaxError.
                exc.__traceback__ = tb.tb_next
            tb = tb.tb_next


def _compose_callable(run_arg: RunArg) -> Callable[[], Any]:
    # TODO: Rewrite with a match statement for Python 3.10
    statement = run_arg.statement
    filename = run_arg.filename

    if isinstance(statement, str):
        assert filename is not None
        code = compile(statement, filename, 'exec')
        return _script.compose(code)
    elif isinstance(statement, Path):
        return _from_path(statement)
    elif isinstance(statement, CodeType):
        return _script.compose(statement)
    elif callable(statement):
        return statement
    else:
        raise TypeError(f'statement: {statement!r}')


def _from_path(path: Path) -> Callable[[], Any]:
    # Read as a str and compile it as Pdb does.
    # https://github.com/python/cpython/blob/v3.10.10/Lib/pdb.py#L1568-L1592
    path = Path(to_canonic_path(str(path)))
    statement = path.read_text()
    code = compile(statement, str(path), 'exec')
    sys.path.insert(0, str(path.parent))
    return _script.compose(code)
