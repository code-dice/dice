import errno
import fcntl
import os
import random
import select
import signal
import subprocess
import time


class CmdResult(object):
    """A class representing the result of a system call.
    """

    def __init__(self, cmdline):
        self.cmdline = cmdline
        self.stdout = ""
        self.stderr = ""
        self.exit_code = None
        self.exit_status = "undefined"
        self.call_time = 0.0

    def __str__(self):
        s = ''
        s += "command: %s\n" % self.cmdline
        s += "stdout:\n%s\n" % self.stdout
        s += "stderr:\n%s\n" % self.stderr
        return s

    def pprint(self):
        """
        Print the command result in a pretty and colorful way.
        """
        _, tty_w = subprocess.check_output(['stty', 'size']).split()

        fmt_str = ('\033[94m%%-%ds\033[93m%%-3s\033[0m%4%.3f' %
                   (int(tty_w) - 16))

        print(fmt_str % (
            self.cmdline, self.exit_status, self.call_time))
        for line in self.stdout.splitlines():
            print(line)
        for line in self.stderr.splitlines():
            print('\033[91m%s\033[0m' % line)


def weighted_choice(choices):
    total = sum(choice.weight for choice in choices)
    rnd_num = random.uniform(0, total)
    upto = 0
    for choice in choices:
        if upto + choice.weight > rnd_num:
            return choice
        upto += choice.weight
    assert False, "Shouldn't get here"


def escape(org_str):
    escapes = """~()[]{}<>|&$#?'"`*; \n\t\r\\"""
    new_str = ""
    for char in org_str:
        if char in escapes:
            new_str += '\\' + char
        else:
            new_str += char
    return new_str


def pids():
    return [pid for pid in os.listdir('/proc') if pid.isdigit()]


def kernel_pids():
    results = []
    for pid in pids():
        try:
            with open(os.path.join('/proc', pid, 'cmdline'), 'rb') as fp:
                if not fp.read():
                    results.append(pid)
        except IOError:
            continue
    return results


def run(cmdline, timeout=10):
    """Run the command line and return the result with a CmdResult object.

    :param cmdline: The command line to run.
    :type cmdline: str.
    :param timeout: After which the calling processing is killed.
    :type timeout: float.
    :returns: CmdResult -- the command result.
    :raises:
    """

    start = time.time()
    process = subprocess.Popen(
        cmdline,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        preexec_fn=os.setsid,
    )

    fcntl.fcntl(
        process.stdout,
        fcntl.F_SETFL,
        fcntl.fcntl(process.stdout, fcntl.F_GETFL) | os.O_NONBLOCK,
    )
    fcntl.fcntl(
        process.stderr,
        fcntl.F_SETFL,
        fcntl.fcntl(process.stderr, fcntl.F_GETFL) | os.O_NONBLOCK,
    )

    result = CmdResult(cmdline)

    try:
        while True:
            exit_code = process.poll()
            result.call_time = (time.time() - start)

            select.select([process.stdout, process.stderr], [], [], 0.1)
            try:
                out_lines = process.stdout.read()
                if out_lines:
                    result.stdout += out_lines
                err_lines = process.stderr.read()
                if err_lines:
                    result.stderr += err_lines
            except IOError as detail:
                if detail.errno != errno.EAGAIN:
                    raise detail

            if exit_code is not None:
                result.exit_code = exit_code
                if exit_code == 0:
                    result.exit_status = "success"
                else:
                    result.exit_status = "failure"
                return result

            if result.call_time > timeout:
                return result
    finally:
        if result.exit_code is None:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
            result.exit_status = "timeout"
