#!/usr/bin/env python2
#
# Copyright 2019 RnD Center "ELVEES", JSC
#

from __future__ import print_function
import argparse
import json
import sys

import serial

import mcom02_flash_tools

__version__ = '2.2.0'

def eprint(*args, **kwargs):
    print('Error:', *args, file=sys.stderr, **kwargs)


def spi_probe(console, spi_bus_cs):
    console.run_with_retcode('sf probe {}:{}'.format(*spi_bus_cs),
                             errmsg='SPI Flash probe error')


def spi_unlock(console):
    rc, _ = console.run_with_retcode('sf protect unlock ${factoryoffset} ${factorysize}',
                                     check=False)
    if rc:
        print('Warning: Can not disable SPI Flash software write protection.\n'
              '  Software write protection is already disabled or write protection jumper is set.\n'
              '  If flashing will fail then check write protection jumper.')


def spi_lock(console):
    console.run_with_retcode('sf protect lock ${factoryoffset} ${factorysize}')


def cmd_flash(console, args):
    keys = []
    for var in args.setting:
        key, value = var
        keys.append(key)
        console.run_with_retcode('setenv {} {}'.format(key, value))

    console.run_with_retcode('env export -c -s ${{factorysize}} ${{loadaddr}} {}'
                             .format(' '.join(keys)))
    spi_probe(console, args.spi)
    spi_unlock(console)
    console.run_with_retcode('sf update ${loadaddr} ${factoryoffset} ${factorysize}',
                             errmsg='Flashing error. Please check write protection jumper.')
    if args.lock:
        spi_lock(console)
    if args.verbose:
        print('')
    print('Factory settings successfully flashed')


def cmd_clear(console, args):
    spi_probe(console, args.spi)
    spi_unlock(console)
    console.run_with_retcode('sf erase ${factoryoffset} ${factorysize}',
                             errmsg='Factory settings clear error. Please check write protection '
                                    'jumper.')
    if args.lock:
        spi_lock(console)
    if args.verbose:
        print('')
    print('Factory settings successfully cleared')


def cmd_print(console, args):

    def get_var_int(name):
        _, resp = console.run_with_retcode('env print {}'.format(name))
        _, value = resp.split('=', 1)
        return int(value, 16)

    # backup original environment
    loadaddr = get_var_int('loadaddr')
    factorysize = get_var_int('factorysize')

    # env_backup_size must be equal to CONFIG_ENV_SIZE but this value is unavailable
    # from U-Boot command line. Using factorysize because factorysize equal to sector size.
    env_backup_size = factorysize
    env_backup_addr = loadaddr + factorysize

    # BUG: env export command will create incorrect buffer if used CONFIG_SYS_REDUNDAND_ENVIRONMENT
    console.run_with_retcode('env export -c -s {:#x} {:#x}'.format(env_backup_size,
                                                                   env_backup_addr))
    spi_probe(console, args.spi)
    console.run_with_retcode('sf read ${loadaddr} ${factoryoffset} ${factorysize}',
                             errmsg='Read from SPI Flash error')
    retcode, _ = console.run_with_retcode('env import -d -c ${loadaddr} ${factorysize}',
                                          check=False)
    if retcode:
        print('{}' if args.json else 'Factory settings sector is null or corrupted')
        return

    _, resp = console.run_with_retcode('env print')

    # restore original environment
    console.run_with_retcode('env import -d -c {:#x} {:#x}'.format(env_backup_addr,
                                                                   env_backup_size))
    resp = resp.split('\n\n')[0]
    if args.verbose:
        print('')
    if args.json:
        variables_list = resp.split('\n')
        variables = {}
        for s in variables_list:
            name, value = s.split('=', 1)
            variables[name] = value
        print(json.dumps(variables, sort_keys=True, indent=4))
    else:
        print('Factory settings:\n')
        print(resp)


if __name__ == '__main__':

    def setting(s):
        res = s.split('=', 1)
        if len(res) != 2:
            raise argparse.ArgumentError
        return res

    description = 'The script to program the SPI flash memory on Salute MCom-02 boards with ' \
                  'factory settings and enable write protection for these settings. ' \
                  'Board must be flashed with U-Boot bootloader and UART0 must be ' \
                  'connected to PC. The board must be powered after the script is started.'
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p', '--port', default='/dev/ttyUSB0',
                        help='TTY port name')
    parser.add_argument('-s', '--spi', type=int, nargs=2, metavar=('bus', 'cs'), default=[0, 0],
                        help='SPI bus and chip select numbers of flash memory on target')
    parser.add_argument('-t', '--timeout', type=int,
                        help='Time in seconds to wait for U-Boot terminal, default - infinite')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='verbose mode (will show all UART transactions)')
    parser.add_argument('--version', action='version', version=__version__)
    subparsers = parser.add_subparsers(dest='command', help='commands')
    parser_flash = subparsers.add_parser('flash',
                                         help='flash factory settings into SPI flash memory',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_flash.add_argument('setting', nargs='+', type=setting, help='settings list')

    parser_clear = subparsers.add_parser('clear', help='clear all factory settings',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    for p in [parser_flash, parser_clear]:
        p.add_argument('-l', '--lock', type=int, choices=[0, 1], default=1,
                       help='if 1 then set write protection')

    parser_print = subparsers.add_parser('print', help='print currently flashed settings')
    parser_print.add_argument('-j', '--json', action='store_true',
                              help='output settings in JSON format')
    args = parser.parse_args()

    try:
        console = mcom02_flash_tools.UART(prompt='\nmcom# ', port=args.port, verbose=args.verbose)
    except serial.SerialException as e:
        eprint(e)
        sys.exit(1)

    show_waiting_status = args.command != 'print' or not args.json
    ok = console.wait_for_uboot(timeout=args.timeout, show_status=show_waiting_status)
    if not ok:
        eprint('Error: U-Boot terminal does not respond. Set the boot mode to SPI '
               'and reset the board power (do not use warm reset).')
        sys.exit(1)
    command_functions = {
        'flash': cmd_flash,
        'clear': cmd_clear,
        'print': cmd_print,
    }
    command_functions[args.command](console, args)
