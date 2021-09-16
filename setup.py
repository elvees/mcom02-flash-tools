#!/usr/bin/env python3
#
# Copyright 2017-2020 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: MIT
#

from setuptools import find_packages
from setuptools import setup

setup(
    name='mcom02_flash_tools',
    description='MCom-02 based PCB flashing tools',
    python_requires='>=3.6,<4.0',
    packages=find_packages(),
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    scripts=['mcom02_flash_tools/mcom02_flash_factory.py',
             'mcom02_flash_tools/mcom02_flash_spi.py',
             'mcom02_flash_tools/mcom02_flash_ums_mmc.py'],
    install_requires=['intelhex>=2.1,<3.0',
                      'pyserial>=3.0,<4.0'],
)
