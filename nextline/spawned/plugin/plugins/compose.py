import sys
from pathlib import Path
from types import CodeType
from typing import Any, Callable

from nextline.spawned import script
from nextline.spawned.plugin.spec import hookimpl
from nextline.spawned.types import RunArg
from nextline.spawned.utils import to_canonic_path


class CallableComposer:
    @hookimpl
    def init(self, run_arg: RunArg) -> None:
        self._run_arg = run_arg

    @hookimpl
    def compose_callable(self) -> Callable[[], Any]:
        return _compose_callable(self._run_arg)


def _compose_callable(run_arg: RunArg) -> Callable[[], Any]:
    # TODO: Rewrite with a match statement for Python 3.10
    statement = run_arg.statement
    filename = run_arg.filename

    if isinstance(statement, str):
        if (path := Path(to_canonic_path(statement))).is_file():
            statement = path

    if isinstance(statement, str):
        assert filename is not None
        code = compile(statement, filename, 'exec')
        return script.compose(code)
    elif isinstance(statement, Path):
        return _from_path(statement)
    elif isinstance(statement, CodeType):
        return script.compose(statement)
    elif callable(statement):
        return statement
    else:
        raise TypeError(f'statement: {statement!r}')


def _from_path(path: Path) -> Callable[[], Any]:
    # Read as a str and compile it as Pdb does.
    # https://github.com/python/cpython/blob/v3.10.10/Lib/pdb.py#L1568-L1592
    statement = path.read_text()
    code = compile(statement, str(path), 'exec')
    sys.path.insert(0, str(path.parent))
    return script.compose(code)
