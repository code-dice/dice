#!/usr/bin/env python

import os
import io
import glob
import logging
import subprocess
from setuptools import setup
from setuptools.command.test import test
import dice


class SelfTest(test):
    def run(self):
        fail = False
        cmds = [
            'coverage run -m unittest discover tests -p *unittest.py'.split(),
            'pylint dice/ scripts/dice --reports=n --disable=R,C,I'.split(),
            'pep8 scripts/dice dice/ --ignore=E501'.split(),
        ]
        for cmd in cmds:
            try:
                subprocess.check_call(cmd)
            except subprocess.CalledProcessError:
                fail = True
                logging.error('Error when running test cmd: %s', ' '.join(cmd))

        if fail:
            exit(1)


def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)


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
        'dice/utils',
    ]
    return packages


setup(
    name='dice',
    version=dice.__version__,
    url='http://github.com/Hao-Liu/dice/',
    license='GNU General Public License v2',
    author='Hao Liu',
    author_email='hliu@redhat.com',
    description='A random testing framework',
    scripts=['scripts/dice'],
    packages=get_packages(),
    data_files=get_data_files(),
    cmdclass={
        'test': SelfTest,
        'check': SelfTest,
    },
)
