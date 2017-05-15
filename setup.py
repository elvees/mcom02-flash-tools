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
    scripts=['mcom_flash_mmc.py'],
    install_requires=['paramiko>=2.1,<3.0'],
)
