#!/usr/bin/env python3

# Copyright 2015-2016 ELVEES NeoTek JSC
# Copyright 2017-2020 RnD Center "ELVEES", JSC

# SPDX-License-Identifier: MIT

import os
import platform
import struct
import sys
from argparse import ArgumentParser
from io import StringIO

from intelhex import IntelHex
from serial import SerialException

from mcom02_flash_tools import UART, __version__, eprint


def send_cmd(tty, cmd):
    res = tty.run(cmd, timeout=10, strip_echo=False)
    if res is None:
        eprint("Device does not respond on {}".format(cmd))
        sys.exit(1)
    if res.strip() == '#':
        eprint("BootROM received empty response")
        sys.exit(1)
    if "Incorrect command" in res:
        eprint("BootROM received incorrect command:\n{}".format(res))
        sys.exit(1)
    if cmd not in res:
        eprint("BootROM received incorrect command arguments:\n{}".format(res))
        sys.exit(1)
    return res


class SPI0Controller(object):
    """Manage SPI controller via MCom-02 BootROM terminal"""

    GATE_SYS_CTR = 0x3809404C
    CLK_SPI0_EN = 1 << 19
    SWPORTD_CTL = 0x3803402C
    CTRL0 = 0x38032000
    CTRL1 = 0x38032004
    SSIENR = 0x38032008
    SER = 0x38032010
    BAUDR = 0x38032014
    TXFTLR = 0x38032018
    RXFTLR = 0x3803201C
    RXFLR = 0x38032024
    DR = 0x38032060
    SS_TOGGLE = 0x380320F4
    FRAME_SIZE_8BIT = 0x7

    def __init__(self, tty):
        self.tty = tty

    def write_reg(self, addr, val):
        # We must not use 0x prefix for hexadecimals.
        # See MCom-02 errata rf#1354
        send_cmd(self.tty, "set {:x} {:x}".format(addr, val))

    def read_reg(self, addr):
        resp = send_cmd(self.tty, "dump {:x} 1".format(addr))
        resp = resp.split('\n')[2:][0]
        return int(resp.split(' : ')[1], 0)

    def __enter__(self):
        """Enable SPI clock, setup pins to SPI mode and setup SPI controller"""
        self.write_reg(self.GATE_SYS_CTR, self.read_reg(self.GATE_SYS_CTR) | self.CLK_SPI0_EN)
        gpiod_ctl_value = (1 << 15) | (1 << 16) | (1 << 17) | (1 << 18)
        self.write_reg(self.SWPORTD_CTL, self.read_reg(self.SWPORTD_CTL) | gpiod_ctl_value)
        self.write_reg(self.SSIENR, 0)
        self.write_reg(self.CTRL0, self.FRAME_SIZE_8BIT)

        # Use very small SPI frequency (1 kHz) because SPI controller will deassert SS signal
        # when TX FIFO will be empty. Data must pass through UART faster than through SPI.
        self.write_reg(self.BAUDR, 24000)
        self.write_reg(self.TXFTLR, 256)
        self.write_reg(self.RXFTLR, 256)
        self.write_reg(self.SS_TOGGLE, 0)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore SPI frequency"""
        self.write_reg(self.BAUDR, 2)  # back SPI frequency to 12 MHz

    def transfer(self, send_data, receive_count):
        """Select SS0, transmit 'send_data' and receive 'receive_count' bytes"""

        def read_byte():
            while self.read_reg(self.RXFLR) == 0:
                pass
            return self.read_reg(self.DR) & 0xFF

        self.write_reg(self.CTRL1, len(send_data) + receive_count)
        self.write_reg(self.SSIENR, 1)
        self.write_reg(self.SER, 0x1)
        for b in send_data:
            self.write_reg(self.DR, b)
        for _ in range(receive_count):
            self.write_reg(self.DR, 0)

        for _ in send_data:
            read_byte()

        rcv_data = []
        for _ in range(receive_count):
            rcv_data.append(read_byte())

        self.write_reg(self.SSIENR, 0)

        return rcv_data


def send_ihex(tty, ihex):
    sio = StringIO()
    ihex.write_hex_file(sio)
    sio.seek(0)
    res = tty.run(sio.read().strip())
    if res is None:
        eprint("The device does not respond on writing a file")
        sys.exit(1)
    return res


def split_bin_to_ihex(file_name, base_addr, max_block_size):
    """Split a binary file to the blocks and load the blocks to IntelHex
    objects. Return the list of IntelHex objects.
    """
    # Block size must be aligned to 2 byte boundary (workaround for rf#2088)
    assert max_block_size % 2 == 0
    ihex_list = []
    with open(file_name, 'rb') as f:
        while True:
            block = bytearray(f.read(max_block_size))
            if not block:
                break
            # Align the last block to 2 byte boundary (workaround for rf#2088)
            if len(block) % 2 != 0:
                block.append(0xFF)
            ihex = IntelHex()
            ihex.frombytes(block, base_addr)
            ihex_list.append(ihex)
    return ihex_list


def write_bin_to_flash(tty, file_name):
    base_addr = 0x20000000
    max_block_size = 0xC000
    ihex_list = split_bin_to_ihex(file_name, base_addr, max_block_size)
    send_cmd(tty, "setflash 0")
    for i, ihex in enumerate(ihex_list):
        print("Block: {}/{}, size: {}".format(i + 1, len(ihex_list), len(ihex)))
        send_ihex(tty, ihex)
        send_cmd(tty, "commitspiflash {:x} {:x}".format(base_addr, len(ihex)))


def dump2bytes(list_string):
    # BootROM rev.0 prints additional string "Config spi0... Ok" before data
    # so we have to filter this string out
    if not list_string[0].startswith("0x"):
        list_string = list_string[1:]

    bytes = bytearray()
    for s in list_string:
        addr, word = s.split(' : ')
        bytes += bytearray(struct.pack('<I', int(word, 0)))
    return bytes


def check_block(tty, data, offset, size):
    dump_count = int((size + 3) / 4)
    dump = send_cmd(tty, "dumpspiflash {:x} {:x}".format(offset, dump_count))
    received = dump2bytes(dump.split("\n")[2:][:-1])
    return received[:size] == data[offset:][:size]


def check_file(tty, file_name, count):
    max_block_size = 0x2000
    with open(file_name, 'rb') as f:
        if count is None:
            data = f.read()
        else:
            data = f.read(count)
    block_count = int((len(data) + max_block_size - 1) / max_block_size)
    for i, block_offset in enumerate(range(0, len(data), max_block_size)):
        block_size = min(max_block_size, len(data) - block_offset)
        print("Block: {}/{}, size: {}".format(i + 1, block_count, block_size))
        if not check_block(tty, data, block_offset, block_size):
            return False
    return True


def unlock_write_protect(tty):
    CMD_WRITE_STATUS_BYTE1 = 0x1
    CMD_WRITE_DISABLE = 0x4
    CMD_WRITE_ENABLE = 0x6
    CMD_READ_MANUF_ID = 0x9F
    MAN_ID_ATMEL = 0x1F
    MAN_ID_MICRON = 0x20
    MANUFACTURERS = {MAN_ID_ATMEL: "Atmel/Adesto", MAN_ID_MICRON: "Micron"}

    with SPI0Controller(tty) as spi:
        flash_id = spi.transfer([CMD_READ_MANUF_ID], 3)
        man_id = flash_id[0]
        man_str = MANUFACTURERS.get(man_id, "Unknown")
        print("SPI Flash manufacturer: {}".format(man_str))
        if man_id == MAN_ID_ATMEL:
            spi.transfer([CMD_WRITE_ENABLE], 0)
            spi.transfer([CMD_WRITE_STATUS_BYTE1, 0], 0)
            spi.transfer([CMD_WRITE_DISABLE], 0)
            print("Software write protect is disabled")


def main():
    if platform.system() == 'Windows':
        default_port = 'COM3'
    else:
        default_port = '/dev/ttyUSB0'

    description = (
        "The script to program the on-board SPI flash memory "
        "with a binary file via MCom-02 Bootrom UART terminal. "
        "The file is written starting from the zero page "
        "of the SPI flash memory."
    )
    parser = ArgumentParser(description=description)
    parser.add_argument("file_name", help="binary file for programming")
    parser.add_argument(
        "-p",
        dest="port",
        default=default_port,
        help="serial port the device is connected to " "(default: %(default)s)",
    )
    parser.add_argument(
        "-c",
        dest="count",
        type=int,
        default=None,
        help="count of data bytes to check after programming, "
        "if not specified all the data is checked "
        "(default: %(default)s)",
    )
    parser.add_argument("--version", action='version', version=__version__)
    args = parser.parse_args()

    file_name = args.file_name
    if not os.path.exists(file_name):
        eprint("File '%s' is not found" % file_name)
        sys.exit(1)

    try:
        tty = UART(prompt='\r#', port=args.port)
    except SerialException:
        eprint("Failed to open device '%s'" % args.port)
        sys.exit(1)

    if tty.run("") is None:
        eprint(
            "Terminal does not respond. Set the boot mode to UART "
            "and reset the board power (do not use warm reset)"
        )
        sys.exit(1)

    # Disable DDR retention to avoid large current on DDRx_VDDQ (see rf#1160).
    send_cmd(tty, "set 38095024 0")

    send_cmd(tty, "autorun 0")
    send_cmd(tty, "cache 1")

    unlock_write_protect(tty)

    print("Writing to flash...")
    write_bin_to_flash(tty, file_name)

    print("Checking...")
    checking_succeeded = check_file(tty, file_name, args.count)

    send_cmd(tty, "cache 0")

    if checking_succeeded:
        print("Checking succeeded")
        sys.exit(0)
    else:
        eprint("Checking failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
