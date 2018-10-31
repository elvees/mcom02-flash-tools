#!/usr/bin/env python2
#
# Copyright 2017-2018 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: MIT
#

from setuptools import setup

setup(
    name='mcom02_flash_tools',
    version='2.1.1',
    description='MCom-02 based PCB flashing tools',
    python_requires='~=2.7',
    scripts=['mcom02_flash_mmc.py',
             'mcom02_flash_spi.py',
             'mcom02_flash_ums_mmc.py'],
    install_requires=['intelhex>=2.1,<3.0',
                      'paramiko==2.2.1',
                      'pyserial>=3.0,<4.0'],
)
