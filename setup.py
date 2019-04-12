#!/usr/bin/env python2
#
# Copyright 2017-2019 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: MIT
#

from setuptools import find_packages
from setuptools import setup

setup(
    name='mcom02_flash_tools',
    version='2.2.0',
    description='MCom-02 based PCB flashing tools',
    python_requires='~=2.7',
    packages=find_packages(),
    scripts=['mcom02_flash_spi.py',
             'mcom02_flash_ums_mmc.py'],
    install_requires=['intelhex>=2.1,<3.0',
                      'monotonic>=1.0,<2.0',
                      'pyserial>=3.0,<4.0'],
)
