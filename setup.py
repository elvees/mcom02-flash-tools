#!/usr/bin/env python
#
# Copyright 2017 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: GPL-2.0+
#

from setuptools import setup

setup(
    name='mcom_flash_tools',
    version='1.0',
    description='MCom flash tools',
    scripts=['mcom_flash_mmc.py',
             'mcom_flash_spi.py'],
    install_requires=['intelhex>=2.1,<3.0',
                      'paramiko>=2.1,<3.0',
                      'pyserial>=2.6,<3.0'],
)
