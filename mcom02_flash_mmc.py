#!/usr/bin/env python
#
# Copyright 2017 RnD Center "ELVEES", JSC
#
# SPDX-License-Identifier: GPL-2.0+
#

from argparse import ArgumentParser
import hashlib

from paramiko import AutoAddPolicy
from paramiko import SSHClient


def write_block(ssh, device, image, block_size, md5):
    size = 0
    buffer_size = 512
    offset = image.tell() / 1048576

    stdin, stdout, stderr = ssh.exec_command('dd of=/tmp/mcom02-flash-mmc')
    while size < block_size:
        buffer = image.read(buffer_size)
        if not buffer:
            break
        stdin.write(buffer)
        size += len(buffer)
        md5.update(buffer)
    stdin.channel.shutdown_write()
    stdout.channel.recv_exit_status()

    stdin, stdout, stderr = ssh.exec_command('dd if=/tmp/mcom02-flash-mmc of=%s bs=1M seek=%d' %
                                             (device, offset))
    stdout.channel.recv_exit_status()

    stdin, stdout, stderr = ssh.exec_command('sync')
    stdout.channel.recv_exit_status()

    stdin, stdout, stderr = ssh.exec_command('rm /tmp/mcom02-flash-mmc')
    stdout.channel.recv_exit_status()

    return size == block_size


def verify_image(ssh, device, image_size, md5):
    stdin, stdout, stderr = ssh.exec_command('dd if=%s bs=512 count=%d | md5sum' %
                                             (device, image_size / 512))

    return stdout.readline().startswith(md5.hexdigest())


if __name__ == '__main__':
    description = 'The script to write a binary image to the MMC device via SSH.'

    parser = ArgumentParser(description=description, prog='mcom_flash_mmc')
    parser.add_argument('hostname',
                        help='the server to connect to')
    parser.add_argument('device',
                        help='the device to write a binary image to')
    parser.add_argument('image',
                        help='a binary image for writing')
    parser.add_argument('--block', default=256, type=int,
                        help='the block size in megabytes for writing (default: %(default)s)')
    parser.add_argument('--port', default=22, type=int,
                        help='the server port to connect to (default: %(default)s)')
    parser.add_argument('--username', default='root',
                        help='the username to authenticate as (default: %(default)s)')
    parser.add_argument('--password', default='root',
                        help='a password to use for authentication (default: %(default)s)')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    args = parser.parse_args()

    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(args.hostname, args.port, args.username, args.password)

    md5 = hashlib.md5()

    print 'Writing...'
    with open(args.image, 'rb') as image:
        while write_block(ssh, args.device, image, args.block * 1048576, md5):
            pass
        image_size = image.tell()
    print 'Done'

    print 'Verifying...'
    if verify_image(ssh, args.device, image_size, md5):
        print 'OK'
    else:
        print 'Fail'

    ssh.close()
