# Copyright 2021 RnD Center "ELVEES", JSC

import pytest
import sh


def pytest_addoption(parser):
    parser.addoption(
        "--dut-term", action="store", default="/dev/ttyUSB4", help="Path to DUT termital tty"
    )
    parser.addoption("--uip-term", action="store", default="/dev/ttyUSB5", help="Path to UIP tty")
    parser.addoption(
        "--uboot-image",
        action="store",
        default="mcom02-uboot.img",
        help="Path to U-boot image file",
    )


@pytest.fixture(scope="session")
def dut_term(request):
    return request.config.getoption("--dut-term")


@pytest.fixture(scope="session")
def uip_term(request):
    yield request.config.getoption("--uip-term")

    # power off PM-UKF
    sh.uip_ctl(uip_term, "switch", "off")


@pytest.fixture(scope="session")
def img_path(request):
    return request.config.getoption("--img")
