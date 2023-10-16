import fnmatch
from collections.abc import Iterable


def match_any(filename: str | None, patterns: Iterable[str]) -> bool:
    '''Test if the filename matches any of the patterns

    This function is based on Bdb.is_skipped_module():
    https://github.com/python/cpython/blob/v3.9.5/Lib/bdb.py#L191
    '''
    if filename is None:
        return False
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)
