#!/usr/bin/env python3
#
# Copyright 2018-2020 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: MIT
#

import argparse
import subprocess
import sys
import time

from mcom02_flash_tools import UART, __version__, eprint

exp_str_timeout = 10
usb_device_init_delay = 5


def uboot_break(tty):
    tty.run('\x03', timeout=exp_str_timeout)  # send Ctrl-C to stop probably running process


def get_block_devices():
    out = subprocess.check_output(
        ['lsblk', '-o', 'name', '--list', '--nodeps'], universal_newlines=True
    )
    return out.split()[1:]


def main():
    description = (
        'This script writes binary images to on-board MMC memory via USB. '
        'On-board USB controller must be connected in USB Device or Device mode '
        'with OTG support. '
        'U-Boot for MCom-02 must be compiled with UMS support. '
        'The board must be connected to the PC via UART (for U-Boot terminal) and USB '
        '(to transfer data). During the launch of the script, '
        'no third-party USB flash drives should be connected to the PC.'
    )

    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('port', help='serial port the device is connected to')
    parser.add_argument('image', help='a binary image for writing')
    parser.add_argument(
        '--mmcdev', default=0, type=int, choices=[0, 1], help='target MMC device on board'
    )
    parser.add_argument(
        '--wait-uboot',
        default=10,
        type=int,
        dest='wait_uboot',
        help='time in seconds to wait for U-Boot terminal, 0 - infinite',
    )
    parser.add_argument('--prompt', default='mcom#', help='U-Boot command line prompt')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--status', action='store_true', help='show progress of dd utility')
    args = parser.parse_args()

    tty = UART(prompt=args.prompt, port=args.port)
    wait_uboot = None if not args.wait_uboot else args.wait_uboot
    ok = tty.wait_for_uboot(timeout=wait_uboot)
    if not ok:
        eprint(
            'U-Boot terminal does not respond. Set the boot mode to SPI '
            'and reset the board power (do not use warm reset).'
        )
        sys.exit(1)
    tty.run('')  # hitting key to stop autoboot

    uboot_version = tty.get_uboot_version()
    if uboot_version is not None:
        print('Found U-Boot: {}'.format(uboot_version))
    else:
        eprint('No U-Boot terminal found.')
        sys.exit(1)

    print('Board model: ', tty.get_uboot_board_model(timeout=exp_str_timeout))
    print('Enabling USB Mass storage on target...')
    block_device_list_before_init = get_block_devices()
    tty.tty.write('ums 0 mmc {}\n'.format(args.mmcdev).encode())
    time.sleep(usb_device_init_delay)

    ok, resp = tty.wait_for_string(
        [
            f'UMS: LUN 0, dev {args.mmcdev}'.format(args.mmcdev),  # for U-Boot < 2021.04
            f'UMS: LUN 0, dev mmc {args.mmcdev}'.format(args.mmcdev),  # for U-Boot >= 2021.04
        ],
        timeout=exp_str_timeout,
    )

    if not ok:
        eprint('Failed to enable UMS for MMC {}. U-Boot response {}.'.format(args.mmcdev, resp))
        sys.exit(1)

    block_device_list_after_init = get_block_devices()
    usb_devices_diff = set(block_device_list_after_init) - set(block_device_list_before_init)
    if len(usb_devices_diff) == 0:
        eprint('No USB device connections from board.')
        sys.exit(1)
    if len(usb_devices_diff) > 1:
        eprint('Too many USB device connections.')
        sys.exit(1)

    board_usb_device = usb_devices_diff.pop()
    print('Writing image {} to /dev/{}...'.format(args.image, board_usb_device))

    cmd = [
        'dd',
        'if={}'.format(args.image),
        'of=/dev/{}'.format(board_usb_device),
        'bs=4M',
        'oflag=direct',
    ]
    if args.status:
        cmd.append('status=progress')
    try:
        process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        process.communicate()
        errcode = process.returncode
    finally:  # terminate child process in case KeyboardInterrupt (Ctrl+C), etc
        if process.poll() is None:
            print('Terminating child process...')
            process.terminate()
            process.kill()

    if errcode:
        eprint('Failed to write image to USB device')
        sys.exit(1)

    uboot_break(tty)
    print("Done")


if __name__ == "__main__":
    main()
