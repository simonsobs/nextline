import errno
import sys
from logging import getLogger
from pathlib import Path
from types import CodeType
from typing import Any, Callable, Optional

from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import RunArg, RunResult
from nextline.spawned.utils import to_canonic_path

from . import _script


class CallableComposer:
    @hookimpl
    def init(self, run_arg: RunArg) -> None:
        self._run_arg = run_arg

    @hookimpl
    def compose_callable(self) -> Callable[[], Any]:
        return _compose_callable(self._run_arg)

    @hookimpl
    def finalize_run_result(self, run_result: RunResult) -> None:
        exc = run_result.exc
        if not exc:
            return
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
        if (path := _to_path(statement)) is not None:
            statement = path

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


def _to_path(statement: str) -> Optional[Path]:
    try:
        path = Path(to_canonic_path(statement))
        return path if path.is_file() else None
    except OSError as exc:
        if exc.errno != errno.ENAMETOOLONG:
            # TODO: Add a unit test
            logger = getLogger(__name__)
            logger.exception('')
        return None


def _from_path(path: Path) -> Callable[[], Any]:
    # Read as a str and compile it as Pdb does.
    # https://github.com/python/cpython/blob/v3.10.10/Lib/pdb.py#L1568-L1592
    statement = path.read_text()
    code = compile(statement, str(path), 'exec')
    sys.path.insert(0, str(path.parent))
    return _script.compose(code)
