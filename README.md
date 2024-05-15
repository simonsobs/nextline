[![PyPI - Version](https://img.shields.io/pypi/v/nextline.svg)](https://pypi.org/project/nextline)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nextline.svg)](https://pypi.org/project/nextline)

[![Test Status](https://github.com/simonsobs/nextline/actions/workflows/unit-test.yml/badge.svg)](https://github.com/simonsobs/nextline/actions/workflows/unit-test.yml)
[![Test Status](https://github.com/simonsobs/nextline/actions/workflows/type-check.yml/badge.svg)](https://github.com/simonsobs/nextline/actions/workflows/type-check.yml)
[![codecov](https://codecov.io/gh/simonsobs/nextline/branch/main/graph/badge.svg)](https://codecov.io/gh/simonsobs/nextline)

# Nextline

_Nextline_ is a DAQ sequencer of the [Observatory Control System
(OCS)](https://github.com/simonsobs/ocs/). Nextline allows line-by-line
execution of concurrent Python scripts, which control telescopes, by multiple
users simultaneously from web browsers.

This package provides the core functionality of Nextline. It is used in
[_nextline-graphql_](https://github.com/simonsobs/nextline-graphql), the
plugin-based framework of the backend API server of Nextline.
