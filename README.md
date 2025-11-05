# Nextline

[![PyPI - Version](https://img.shields.io/pypi/v/nextline.svg)](https://pypi.org/project/nextline)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nextline.svg)](https://pypi.org/project/nextline)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.11451619.svg)](https://doi.org/10.5281/zenodo.11451619)


[![Test Status](https://github.com/simonsobs/nextline/actions/workflows/unit-test.yml/badge.svg)](https://github.com/simonsobs/nextline/actions/workflows/unit-test.yml)
[![Test Status](https://github.com/simonsobs/nextline/actions/workflows/type-check.yml/badge.svg)](https://github.com/simonsobs/nextline/actions/workflows/type-check.yml)
[![codecov](https://codecov.io/gh/simonsobs/nextline/branch/main/graph/badge.svg)](https://codecov.io/gh/simonsobs/nextline)

**Note on codecov coverage**: The codecov coverage shown in the badge above is underestimated
because _nextline_ uses the [trace function](https://docs.python.org/3/library/sys.html#sys.settrace). The real coverage is much higher than what
codecov reports.

---

_Nextline_ is a DAQ sequencer of the [Observatory Control System
(OCS)](https://github.com/simonsobs/ocs/). Nextline allows line-by-line
execution of concurrent Python scripts, which control telescopes, by multiple
users simultaneously from web browsers.

This package provides the core functionality of Nextline. It is used in
[_nextline-graphql_](https://github.com/simonsobs/nextline-graphql), the
plugin-based framework of the backend API server of Nextline.
