# Copyright 2019 RnD Center "ELVEES", JSC

from __future__ import print_function
import sys

import monotonic
import serial


class CommandError(Exception):
    pass


class UART(object):
    """Class for work with UART console.
    """

    def __init__(self, prompt, port, newline='\n', verbose=False, baudrate=115200, timeout=0.5):
        """Parameters
        ----------
        prompt : str
            expected command line prompt
        port : str
            serial port for use (example: /dev/ttyUSB0)
        newline : str
            new line delimeter
        verbose : bool
            if True then will show UART transactions
        baudrate : int
            UART speed in bit/sec
        timeout : float
            timeout for read() operations and affects the accuracy of the command execution time
        """
        self.prompt = prompt
        self.newline = newline
        self.verbose = verbose
        self.tty = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def wait_for_string(self, expected, timeout=1):
        """Method to wait for pattern `expected` to be received from UART.

        Parameters
        ----------
        expected : list or str
            string or list of strings for wait.
        timeout : float
            time in seconds. If function does not receive string `expected` in this time then will
            return with False. If None then will wait infinite for expected string.

        Returns
        -------
        bool
            True if pattern `expected` was received
        str
            received data
        """

        def endswith(resp, expected):
            if not isinstance(expected, (list, tuple)):
                expected = (expected, )

            return any(map(resp.endswith, expected))

        if timeout is not None:
            time_end = monotonic.monotonic() + timeout
        else:
            time_end = sys.float_info.max
        resp = ''
        while (monotonic.monotonic() <= time_end) and not endswith(resp, expected):
            ch = self.tty.read(1)
            if not ch:
                continue
            resp += ch

        result = resp.replace('\r', '')
        if self.verbose:
            print(result, end='')
        if not endswith(resp, expected):
            return False, result

        return True, result

    def run(self, cmd, timeout=5, strip_echo=True):
        """Run command and wait for prompt.

        Parameters
        ----------
        cmd : str
            command
        timeout : float
            argument for wait_for_string()
        strip_echo : bool
            if true then will remove echo from response string

        Returns
        -------
        str
            response string
        """
        self.tty.write('{}{}'.format(cmd, self.newline))
        success, resp = self.wait_for_string(self.prompt, timeout)
        if not success:
            return None

        # Return only output of command (without cmd + "\n" and command prompt)
        return resp[len(cmd) + 1: -len(self.prompt)] if strip_echo else resp

    def run_with_retcode(self, cmd, timeout=5, strip_echo=True, check=True, errmsg=None):
        """Run command and wait for prompt. Return retcode and result.

        Parameters
        ----------
        cmd : str
            command
        timeout : float
            argument for wait_for_string()
        strip_echo : bool
            if true then will remove echo from response string
        check : bool
            if True then will raise exception if command return non-zero retcode
        errmsg : string
            message for output when received non-zero retcode (used only with check=True)

        Returns
        -------
        int
            return code of command
        str
            response string
        """
        result = self.run(cmd, timeout, strip_echo)
        resp = self.run('echo $?')
        if resp is None:
            raise CommandError('UART timeout at command "echo $?" after "{}"'.format(cmd))

        retcode = int(resp)
        if check and retcode:
            if errmsg is None:
                errmsg = 'Command "{}" failed'.format(cmd)
            raise CommandError('{}\nTarget answer:\n{}'.format(errmsg, result))

        return retcode, result

    def get_uboot_board_model(self, timeout=5):
        self.run("fdt addr $fdtcontroladdr", timeout=timeout)
        model = self.run("fdt list / model", timeout=timeout)
        try:
            return model.split('=')[1].strip()
        except Exception:
            return None

    def get_uboot_version(self):
        version = self.run('version')
        try:
            return [x.strip() for x in version.split('\n') if x.startswith('U-Boot')][0]
        except Exception:
            return None
