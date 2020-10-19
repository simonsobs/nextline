from setuptools import setup, find_packages
import versioneer

from pathlib import Path

here = Path(__file__).resolve().parent
long_description = here.joinpath('README.md').read_text()

setup(
    name='nextline',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='A Python library for controlling Python scripts execution',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Simons Observatory',
    author_email='so_software@simonsobservatory.org',
    url='https://github.com/simonsobs/nextline',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    packages=find_packages(exclude=['docs', 'tests']),
    include_package_data=True,
    install_requires=[
        'janus>=0.6'
    ],
    extras_require={
        'tests': [
            'pytest>=5.4',
            'pytest-cov>=2.8',
            'snapshottest>0.5'
        ]
    }
)
