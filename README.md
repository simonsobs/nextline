# Nextline

[![PyPI - Version](https://img.shields.io/pypi/v/nextline.svg)](https://pypi.org/project/nextline)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nextline.svg)](https://pypi.org/project/nextline)


[![Test Status](https://github.com/nextline-dev/nextline/actions/workflows/unit-test.yml/badge.svg)](https://github.com/nextline-dev/nextline/actions/workflows/unit-test.yml)
[![Test Status](https://github.com/nextline-dev/nextline/actions/workflows/type-check.yml/badge.svg)](https://github.com/nextline-dev/nextline/actions/workflows/type-check.yml)
[![codecov](https://codecov.io/gh/nextline-dev/nextline/branch/main/graph/badge.svg)](https://codecov.io/gh/nextline-dev/nextline)

**Note on codecov coverage**: The codecov coverage shown in the badge above is underestimated
because _nextline_ uses the [trace function](https://docs.python.org/3/library/sys.html#sys.settrace). The real coverage is much higher than what
codecov reports.

---

This library executes Python scripts under control with trace functions. It
calls callback functions at various events during the execution of the scripts.
