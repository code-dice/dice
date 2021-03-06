#!/usr/bin/env python
"""
DICE is a black-box random testing framework. It aims to help testers random
 testing a project while exploring its feature by writing some constraints.
"""

import os

from setuptools import setup

import dice


def get_config_dir():
    settings_system_wide = os.path.join('/etc')
    settings_local_install = os.path.join('etc')
    if 'VIRTUAL_ENV' in os.environ:
        return settings_local_install
    else:
        return settings_system_wide


def get_data_files():
    data_files = [(get_config_dir(), ['etc/dice.conf'])]
    return data_files


def get_packages():
    packages = [
        'dice',
        'dice/core',
        'dice/client',
        'dice/utils',
    ]
    return packages


setup(
    name='dice',
    version=dice.__version__,
    url='http://github.com/code-dice/dice/',
    license='GNU General Public License v2',
    author='Hao Liu',
    author_email='hliu@redhat.com',
    description='A random testing framework',
    long_description=__doc__,
    scripts=['scripts/dice'],
    packages=get_packages(),
    # Config file will be introduced later.
    # Currently this does nothing but fail rtd build.
)
