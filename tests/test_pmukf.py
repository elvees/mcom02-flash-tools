# Copyright 2021 RnD Center "ELVEES", JSC

import os

import pytest
import sh


def gen_image(file_name, size_bytes):
    with open(file_name, "wb") as fout:
        fout.write(os.urandom(size_bytes))


@pytest.mark.noboard
def test_help_version():
    sh.mcom02_flash_spi("--help")
    sh.mcom02_flash_spi("--version")
    sh.mcom02_flash_factory("--help")
    sh.mcom02_flash_factory("--version")
    sh.mcom02_flash_ums_mmc("--help")
    sh.mcom02_flash_ums_mmc("--version")


# As per rf#2088 there is a bug that BootROM can't write images with odd number of bytes.
# Check flash tool works around this.
@pytest.mark.parametrize(
    "size",
    [
        pytest.param(30 * 1024 + 1, id="odd image (30 KB + 1 B)"),
        pytest.param(30 * 1024 + 3, id="odd image (30 KB + 3 B)"),
        pytest.param(30 * 1024 + 5, id="odd image (30 KB + 5 B)"),
        pytest.param(30 * 1024 + 7, id="odd image (30 KB + 7 B)"),
        pytest.param(30 * 1024 + 8, id="even image (30 KB + 8 B)"),
    ],
)
def test_flash(uip_term, dut_term, tmp_path, size):
    sh.uip_ctl(uip_term, "switch", "off")
    sh.uip_ctl(uip_term, "switch", "on", "--boot", "uart")

    file_name = tmp_path / "test_file.img"
    gen_image(file_name, size)

    sh.mcom02_flash_spi("-p", dut_term, file_name)


def test_factory_settings(uip_term, dut_term, img_path):
    """Check board is flashed with factory settings and they can be read with the tool"""
    sh.uip_ctl(uip_term, "switch", "off")
    sh.uip_ctl(uip_term, "switch", "on", "--boot", "uart")
    # Flash U-Boot as it is required to read factory settings
    sh.mcom02_flash_spi("-c", "0", "-p", dut_term, img_path)

    sh.uip_ctl(uip_term, "switch", "off")
    sh.uip_ctl(uip_term, "switch", "on", "--boot", "spi")
    sh.mcom02_flash_factory("-t 30", "-p", dut_term, "print")
