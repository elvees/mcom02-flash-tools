#!/usr/bin/env python2
#
# Copyright 2018 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: MIT
#

from __future__ import print_function

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
import subprocess
import sys
import time

import serial

__version__ = '2.1.1'

exp_str_timeout = 10
usb_device_init_delay = 5


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def wait_for_string(tty, expected, timeout=10):
    time_end = time.time() + timeout

    def wait():
        if not timeout:
            return True
        return time.time() <= time_end

    resp = ''
    while wait():
        ch = tty.read(1)
        if (ch is None) or (ch == ''):
            continue
        if resp.endswith(expected):
            return True, resp
        resp += ch

    return False, resp


def get_uboot_board_model(tty, prompt):
    run_command(tty, "fdt addr $fdtcontroladdr", prompt)
    model = run_command(tty, "fdt list / model", prompt)
    try:
        return model.split('=')[1].strip()
    except Exception:
        return None


def uboot_break(tty, prompt):
    run_command(tty, '\x03', prompt)  # send Ctrl-C to stop probably running process


def get_uboot_version(tty, prompt):
    version = run_command(tty, 'version', prompt)
    try:
        return [x.strip() for x in version.split('\n') if x.startswith('U-Boot')][0]
    except Exception:
        return None


def run_command(tty, cmd, prompt, timeout=exp_str_timeout):
    tty.reset_input_buffer()
    tty.write('{}\n'.format(cmd))
    success, resp = wait_for_string(tty, prompt, timeout)
    if not success:
        raise IOError('UART timeout')
    # Return only output of command (without cmd + '\r\n' and command prompt)
    return resp[len(cmd) + 2: -len(prompt)]


def get_block_devices():
    out = subprocess.check_output(['lsblk', '-o', 'name', '--list', '--nodeps'])
    return out.split()[1:]


if __name__ == '__main__':
    description = (
        'This script writes binary images to on-board MMC memory via USB. '
        'On-board USB controller must be connected in USB Device or Device mode '
        'with OTG support. '
        'U-Boot for MCom-02 must be compiled with UMS support. '
        'The board must be connected to the PC via UART (for U-Boot terminal) and USB '
        '(to transfer data). During the launch of the script, '
        'no third-party USB flash drives should be connected to the PC.')

    parser = ArgumentParser(description=description,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('port',
                        help='serial port the device is connected to')
    parser.add_argument('image',
                        help='a binary image for writing')
    parser.add_argument('--mmcdev', default=0, type=int, choices=[0, 1],
                        help='target MMC device on board')
    parser.add_argument('--wait-uboot', default=10, type=int,
                        dest='wait_uboot',
                        help='time in seconds to wait for U-Boot terminal, 0 - infinite')
    parser.add_argument('--prompt', default='mcom#',
                        help='U-Boot command line prompt')
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args()

    tty = serial.Serial(port=args.port, baudrate=115200, timeout=0.5)
    ok, _ = wait_for_string(tty, 'Hit any key to stop autoboot', timeout=args.wait_uboot)
    if not ok:
        eprint('Error: U-Boot terminal does not respond. Set the boot mode to SPI '
               'and reset the board power (do not use warm reset).')
        sys.exit(1)
    run_command(tty, 'a', args.prompt)  # hitting key to stop autoboot

    uboot_version = get_uboot_version(tty, args.prompt)
    if uboot_version is not None:
        print('Found U-Boot: {}'.format(uboot_version))
    else:
        eprint('Error: no U-Boot terminal found.')
        sys.exit(1)

    print('Board model: ', get_uboot_board_model(tty, args.prompt))
    print('Enabling USB Mass storage on target...')
    block_device_list_before_init = get_block_devices()
    tty.write('ums 0 mmc {}\n'.format(args.mmcdev))
    time.sleep(usb_device_init_delay)
    ok, resp = wait_for_string(tty, 'UMS: LUN 0, dev {}'.format(args.mmcdev))
    if not ok:
        eprint('Error: failed to enable UMS for MMC {}. U-Boot response {}.'
               .format(args.mmcdev, resp))
        sys.exit(1)

    block_device_list_after_init = get_block_devices()
    usb_devices_diff = set(block_device_list_after_init) - set(block_device_list_before_init)
    if len(usb_devices_diff) == 0:
        eprint('Error: no USB device connections from board.')
        sys.exit(1)
    if len(usb_devices_diff) > 1:
        eprint('Error: too many USB device connections.')
        sys.exit(1)

    board_usb_device = usb_devices_diff.pop()
    print('Writing image to /dev/{}...'.format(board_usb_device))
    try:
        process = subprocess.Popen(
            ['dd', 'if={}'.format(args.image), 'of=/dev/{}'.format(board_usb_device),
             'bs=4M', 'oflag=direct', 'status=progress'],
            stdout=sys.stdout, stderr=sys.stderr)
        process.communicate()
        errcode = process.returncode
    finally:  # terminate child process in case KeyboardInterrupt (Ctrl+C), etc
        if process.poll() is None:
            print('Terminating child process...')
            process.terminate()
            process.kill()

    if errcode:
        eprint('Error: error while writing image to USB device')
        sys.exit(1)

    uboot_break(tty, args.prompt)
    print('Done')
