
##__________________________________________________________________||
__all__ = ['Nextline', 'run_pdb', 'control_pdb']

from .main import Nextline

from .run import run_pdb
from .control import control_pdb

##__________________________________________________________________||
from ._version import get_versions
__version__ = get_versions()['version']
"""str: version

The version string, e.g., "0.1.2", "0.1.2+83.ga093a20.dirty".
generated from git tags by versioneer.

Versioneer: https://github.com/warner/python-versioneer

"""

del get_versions

##__________________________________________________________________||
