#!/usr/bin/env python3
import argparse
import serial
import time
import sys
import os
import select
from enum import Enum
from typing import Optional

EOL = b'\r\n'
DEFAULT_BAUD_RATE = 115200
DEFAULT_TIMEOUT = 5
DEFAULT_TERMINATOR = EOL + b'>>> '

ST_TYPE_FILE = 32768
ST_TYPE_DIRECTORY = 16384

IDENT = '    '
MAX_WRITE_PER_PASS = 64
MAX_READ_PER_PASS = 64

# http://www.physics.udel.edu/~watson/scen103/ascii.html
CTRL_A = b'\x01'
CTRL_B = b'\x02'
CTRL_C = b'\x03'
CTRL_D = b'\x04'
CTRL_E = b'\x05'
CTRL_F = b'\x06'
CTRL_G = b'\x07'


class Commands(Enum):
    RESET = "reset"
    LS = "ls"
    MKDIR = "mkdir"
    MAKEDIRS = "makedirs"
    RMTREE = "rmtree"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    EXECUTE_FILE = "execute_file"
    EXECUTE = "execute"
    LIVE_TEST_FILE = "live_test_file"


VALID_COMMANDS = []
for item in Commands:
    VALID_COMMANDS.append(item.value)


class StatResult:
    def __init__(self, st):
        if st[0] == ST_TYPE_FILE:
            self.isfile = True
            self.isdir = False
        elif st[0] == ST_TYPE_DIRECTORY:
            self.isfile = False
            self.isdir = True
        else:
            raise Exception("Not a file and not a directory?")
        self.size = st[6]


class EspException(Exception):
    def __init__(self, message):
        self.message = message

    def last_line(self):
        lines = self.message.split("\n")
        if len(lines):
            return lines[-1]
        else:
            return None

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.last_line()))


class EspSyncer:
    def __init__(self, ser: serial.Serial, timeout, logger):
        self.ser = ser
        self.timeout = timeout
        self.buffer = b''
        self.logger = logger
        self.os_imported = False

    def reset(self, esp32r0_delay=False):
        # See https://github.com/espressif/esptool/blob/master/esptool.py#L411 - these are active low

        self.ser.setDTR(False)  # IO0=HIGH
        self.ser.setRTS(True)  # EN=LOW, chip in reset
        time.sleep(0.5)
        self.ser.setRTS(False)  # EN=LOW, chip in reset
        data = self.recv(b">>>")

    def send(self, data):
        """Send data to MicroPython prompt.

        The data parameter should end with EOL unless you want to send data in multiple steps."""
        idx = 0
        while idx < len(data):
            idx += self.ser.write(data[idx:])

    def recv(self, terminator=DEFAULT_TERMINATOR):
        """Receive data from MicroPython prompt.

        This receives data until the given terminator."""
        started = time.time()
        while terminator not in self.buffer:
            data = self.ser.read()
            self.buffer += data
            elapsed = time.time() - started
            if self.timeout is not None and elapsed > self.timeout:
                raise TimeoutError

        idx = self.buffer.find(terminator)
        chunk = self.buffer[:idx]
        self.buffer = self.buffer[idx + len(terminator):]
        return chunk

    def dump(self):
        while True:
            data = self.ser.read()
            try:
                s = data.decode("ascii")
            except UnicodeDecodeError:
                s = repr(s)
                sys.stdout.write(s)
                sys.stdout.flush()

    def enter_raw_mode(self):
        # http://www.physics.udel.edu/~watson/scen103/ascii.html
        self.send(CTRL_A)
        self.recv(terminator=b'raw REPL; CTRL-B to exit')

    def enter_paste_mode(self):
        self.send(CTRL_E)

    def exit_paste_mode(self):
        self.send(CTRL_D)

    def communicate(self, stdin, stdout, sdtin_encoding=None, stdout_encoding=None,
                    absolute_timeout=None, timeout=1, paste_mode=True, watch_file_path=None,
                    no_select=False):
        """Communicate with device. Connects stdin and stdout with the serial line of the device.

        :param stdin: Input file (file-like object)
        :param stdout: Output file (file-like ojbect)
        :param sdtin_encoding: If the input file is not binary, then specify its encoding here
        :param sdtin_encoding: If the input file is not binary, then specify its encoding here
        :param stdout_is_binary: If the output file is not binary, then specify its encoding here.
        :param absolute_timeout: Absolute timeout for communication.Effective ONLY when it is not None.
        :param timeout: Timeout between read/write operations. None means infinite.
        :param paste_mode: Post all data in paste mode, then exit paste mode. In this mode, we presume
            that the whole input file can be read within 1 second.
        :param watch_file_path: When specified, it should be a file path. This file will be monitored, and when it
            is changed, then communicate() will return True. This can be used to continuously monitor
            for file changes of test scripts, and re-execute them on the MCU when they are changed.
        :param no_select: When this flag is set, the input file is read at once. When this flag is not set (default),
            the input file is read continuously when data is available (it is checked with select.select).
        """
        if paste_mode:
            self.enter_paste_mode()
        sendbuf = b''
        started, absolute_elapsed = time.time(), 0
        last_comm, elapsed = started, 0
        eof_reached = False
        paste_mode_exited = False
        if watch_file_path:
            last_changed = os.stat(watch_file_path).st_mtime
        else:
            last_changed = 0
        if no_select:
            sendbuf = stdin.read()
            eof_reached = True
        while True:
            was_comm = False

            if not no_select:
                # stdin -> buf
                rlist, wlist, xlist = select.select([stdin], [], [], 0.01)
                if rlist:
                    data = stdin.read()
                    if data:
                        was_comm = True
                        if sdtin_encoding:
                            data = data.decode(sdtin_encoding)
                        sendbuf += data
                    elif not sendbuf:
                        # select.select returns the file, but it reads as an empty string -> EOF reached.
                        if not eof_reached:
                            eof_reached = True

            if eof_reached and not paste_mode_exited:
                sendbuf += CTRL_D  # exit paste mode
                paste_mode_exited = True

            # buf -> MCU
            if sendbuf:
                sent = self.ser.write(sendbuf)
                sendbuf = sendbuf[sent:]
                was_comm = True

            # MCU -> stdout
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                if stdout_encoding:
                    stdout.write(data.decode(stdout_encoding))
                else:
                    stdout.write(data)
                stdout.flush()
                was_comm = True

            now = time.time()
            absolute_elapsed = now - started
            if was_comm:
                last_comm, elapsed = now, 0
            else:
                elapsed = now - last_comm

            if absolute_timeout is not None:
                if absolute_timeout < absolute_elapsed:
                    raise TimeoutError("AbsoluteTimeoutError")

            if timeout is not None:
                if timeout < elapsed:
                    raise TimeoutError("TimeoutError")

            if watch_file_path:
                changed = os.stat(watch_file_path).st_mtime
                if changed != last_changed:
                    return True

    def __call__(self, cmd, terminator=DEFAULT_TERMINATOR, expect_echo=True):
        """Send a single line of command and return the result."""
        cmd = cmd.encode('ascii')
        if not cmd.endswith(EOL):
            cmd += EOL
        self.send(cmd)
        result = self.recv(terminator)
        if expect_echo:
            assert result.startswith(cmd)
            result = result[len(cmd):]
        result = result.decode('ascii')
        if result.startswith('Traceback (most recent call last):'):
            raise EspException(result)
        return result

    def eval(self, cmd):
        """Similar to __call__ but it interprets the result as a python data structure source."""
        if not self.os_imported:
            self("import os", expect_echo=False)
            self.os_imported = True
        return eval(self(cmd))

    def ls(self, relpath):
        return self.eval("os.listdir(%s)" % repr(relpath))

    def rm(self, relpath):
        assert self.eval("os.remove(%s) or True" % repr(relpath)) is True

    def rmdir(self, relpath):
        assert self.eval("os.rmdir(%s) or True" % repr(relpath)) is True

    def mkdir(self, relpath):
        assert self.eval("os.mkdir(%s) or True" % repr(relpath)) is True

    def makedirs(self, realpath):
        assert realpath.startswith("/")
        parts = realpath[1:].split("/")
        for idx in range(len(parts)):
            path = "/" + "/".join(parts[:idx + 1])
            st = self.stat(path)
            if st is None:
                self.mkdir(path)
            elif not st.isdir:
                raise Exception(
                    "Wanted to create directory %s but it already exists and it is not a directory." %
                    path
                )

    def stat(self, relpath) -> Optional[StatResult]:
        try:
            st = self.eval("os.stat(%s)" % repr(relpath))
            return StatResult(st)
        except EspException as e:
            last_line = e.last_line()
            if last_line and last_line.endswith('ENOENT'):
                return None
            else:
                raise e

    def rmtree(self, relpath, ident=''):
        """Delete all files and directories from the flash.

            To wipe out the complete fs: wipe("/")
            To delete the directory "www" and everything inside: wipe("/www")

            Please note that relpath must always be absolute (start with /),
            and it must not end with "/", except when you want to erase the
            whole flash drive.
        """
        # Normalize path
        assert relpath and relpath.startswith('/')
        if relpath != "/" and relpath.endswith("/"):
            relpath = relpath[:-1]

        st = self.stat(relpath)

        if st.isfile:
            self.logger(ident + "RM " + relpath + "\n")
            self.rm(relpath)
        elif st.isdir:
            for fname in sorted(self.ls(relpath)):
                if relpath == '/':
                    fpath = "/" + fname
                else:
                    fpath = relpath + "/" + fname
                self.rmtree(fpath)
            if relpath != "/":
                self.logger(ident + "RMDIR " + relpath + "\n")
                self.rmdir(relpath)

    def _upload_file(self, src, dst, overwrite, quick):
        """Internal method, to not use directly."""
        st = self.stat(dst)
        if st and not overwrite:
            raise Exception("Destination %s already exist." % dst)
        if st and st.isdir:
            raise Exception("Cannot overwrite a directory with a file: %s -> %s" % (src, dst))
        with open(src, "rb") as fin:
            data = fin.read()

        if quick:
            src_size = os.stat(src).st_size
            if st is not None and src_size == st.size:
                self.logger('SKIP ' + dst + '\n')
                return

        self.logger('UPLOAD ' + dst + '\n    ')
        self("_fout = open(%s,'wb+')" % repr(dst), expect_echo=False)
        lcnt = 0
        full_size = len(data)
        total_written = 0
        while data:
            written = self.eval("_fout.write(%s)" % repr(data[:MAX_WRITE_PER_PASS]))
            total_written += written
            data = data[written:]
            self.logger('.')
            lcnt += 1
            if lcnt % 16 == 0:
                percent = 100.0 * total_written / full_size
                self.logger(' %.2fK, %.2f%% \n    ' % (total_written / 1024.0, percent))
        self("_fout.close()", expect_echo=False)
        self("del _fout", expect_echo=False)
        self.logger(' -- %.2f KB OK\n' % (total_written / 1024.0))

    def _upload(self, src, dst, overwrite, quick):
        fname = os.path.split(src)[1]
        if dst == "/":
            dst_path = "/" + fname
        else:
            dst_path = dst + "/" + fname

        if os.path.isdir(src):
            st = self.stat(dst_path)
            if st is None:
                self.logger("MKDIR " + dst_path + "\n")
                self.mkdir(dst_path)
            elif st.isfile:
                raise Exception("upload: cannot overwrite a file with a directory: %s -> %s" % (src, dst))

            for fname in sorted(os.listdir(src)):
                if fname not in [os.pardir, os.curdir]:
                    self._upload(os.path.join(src, fname), dst_path, overwrite, quick)
        elif os.path.isfile(src):
            self._upload_file(src, dst_path, overwrite, quick)
        else:
            raise Exception("Source is not a regular file or directory: %s" % src)

    def upload(self, src, dst, contents, overwrite, quick):
        """Upload local files to the device.

        :param src: Source directory or file to be uploaded.
        :param dst: Destination directory. It must exist!
        :param contents: Set flag to upload the contents of the source dir, instead of the directory itself.
            When set, src must be a directory.
        :param overwrite: Set this flag if you want to automatically overwrite existing files.
        :param quick: Copy only if size differs
        """
        st = self.stat(dst)
        if st is not None and not st.isdir:
            raise Exception("upload: cannot upload to non-existent directory %s" % dst)

        if contents:
            if not os.path.isdir(src):
                raise Exception("upload: --contents was given but the source %s is not a directory" % src)
            for fname in sorted(os.listdir(src)):
                if fname not in [os.pardir, os.curdir]:
                    self._upload(os.path.join(src, fname), dst, overwrite, quick)
        else:
            self._upload(src, dst, overwrite, quick)

    def _download_file(self, src, dst, overwrite, quick):
        """Internal method, to not use directly."""
        if os.path.isdir(dst):
            raise Exception("Cannot overwrite a directory with a file: %s -> %s" % (src, dst))
        if os.path.isfile(dst) and not overwrite:
            raise Exception("Destination file %s already exist." % dst)

        if quick:
            st = self.stat(src)
            if st is not None:
                if os.path.isfile(dst):
                    dst_size = os.stat(dst).st_size
                    if dst_size == st.size:
                        self.logger('SKIP ' + dst + '\n')
                        return

        self("_fin = open(%s,'rb')" % repr(src), expect_echo=False)
        self.logger('DOWNLOAD ' + dst + '\n    ')
        with open(dst, "wb+") as fout:
            lcnt = 0
            total_read = 0
            while True:
                data = self.eval("_fin.read(%s)" % repr(MAX_READ_PER_PASS))
                if not data:
                    break
                fout.write(data)
                lcnt += 1
                self.logger('.')
                if lcnt % 16 == 0:
                    self.logger(' %.2fK \n    ' % (total_read / 1024.0))
                total_read += len(data)

        self("_fin.close()", expect_echo=False)
        self("del _fin", expect_echo=False)
        self.logger(' -- %.2f KB OK\n' % (total_read / 1024.0))

    def _download(self, src, dst, overwrite, quick):
        fname = os.path.split(src)[1]
        # Ez csak unix-on....
        if dst == "/":
            dst_path = "/" + fname
        else:
            dst_path = os.path.join(dst, fname)

        st = self.stat(src)

        if st.isdir:
            if not os.path.isfile(dst_path) and not os.path.isdir(dst_path):
                self.logger("MKDIR " + dst_path + "\n")
                os.mkdir(dst_path)
            elif os.path.isfile(dst_path):
                raise Exception("upload: cannot overwrite a file with a directory: %s -> %s" % (src, dst))

            for fname in sorted(self.ls(src)):
                if fname not in [".", ".."]:
                    if src == "/":
                        src_path = "/" + fname
                    else:
                        src_path = src + "/" + fname
                    self._download(src_path, dst_path, overwrite, quick)
        else:
            self._download_file(src, dst_path, overwrite, quick)

    def download(self, src, dst, contents, overwrite, quick):
        """Download files from device.

        :param src: Source directory or file to be uploaded.
        :param dst: Destination directory. It must exist!
        :param contents: Set flag to download the contents of the source dir, instead of the directory itself.
            When set, src must be a directory.
        :param overwrite: Set this flag if you want to automatically overwrite existing files.
        :param quick: set flag to skip files that have the same size on both devices
        """
        if not os.path.isdir(dst):
            raise Exception("download: cannot download to non-existent directory %s" % dst)

        if contents:
            st = self.stat(src)
            if not st or not st.isdir:
                raise Exception("download: --contents was given but the source %s is not a directory" % src)
            for fname in sorted(self.ls(src)):
                if fname not in ["..", "."]:
                    self._download(src + "/" + fname, dst, overwrite, quick)
        else:
            self._download(src, dst, overwrite, quick)


class Main:
    def __init__(self, args):
        self.args = args

    def log(self, s):
        if self.args.verbose:
            sys.stdout.write(s)
            sys.stdout.flush()

    def run(self, command, params):
        started = time.time()
        with serial.Serial(self.args.port, baudrate=self.args.baudrate, timeout=self.args.timeout) as ser:
            syncer = EspSyncer(ser, self.args.timeout, self.log)
            syncer.reset()
            if command == Commands.RESET.value:
                # syncer.reset()
                pass
            elif command == Commands.LS.value:
                print(syncer.ls(params[0]))
            elif command == Commands.MKDIR.value:
                self.log("MKDIR " + params[0] + "\n")
                syncer.mkdir(params[0])
            elif command == Commands.MAKEDIRS.value:
                self.log("MAKEDIRS " + params[0] + "\n")
                syncer.makedirs(params[0])
            elif command == Commands.RMTREE.value:
                syncer.rmtree(params[0])
            elif command == Commands.UPLOAD.value:
                syncer.upload(params[0], params[1], self.args.contents, self.args.overwrite, self.args.quick)
            elif command == Commands.DOWNLOAD.value:
                syncer.download(params[0], params[1], self.args.contents, self.args.overwrite, self.args.quick)
            elif command in [Commands.EXECUTE_FILE.value, Commands.LIVE_TEST_FILE.value]:
                if args.output:
                    if args.output == "-":
                        fout = sys.stdout
                        stdout_encoding = "utf-8"
                    else:
                        fout = open(args.output, "ba")
                        stdout_encoding = None
                else:
                    fout = None
                    stdout_encoding = None
                if not params:
                    raise SystemExit("execute_file takes a filename argument (or use '--' for stdin)")
                watch_file_path = None
                if params[0] == "-":
                    fin = sys.stdin
                    stdin_encoding = "utf-8"
                    is_regular_file = False
                    if command == Commands.LIVE_TEST_FILE.value:
                        raise SystemExit("cannot live test stdin, it would not be possible to watch for changes")
                else:
                    fin = open(params[0], "rb")
                    stdin_encoding = None
                    is_regular_file = True
                    if command == Commands.LIVE_TEST_FILE.value:
                        watch_file_path = params[0]
                while True:
                    rerun = syncer.communicate(fin, fout, stdin_encoding, stdout_encoding,
                                               watch_file_path=watch_file_path, no_select=is_regular_file,
                                               timeout=args.timeout)
                    if rerun:
                        fin.close()
                        fin = open(params[0], "rb")
                        syncer.reset()
                    else:
                        break

            elif command == Commands.EXECUTE.value:
                self.log(params[0])
                syncer(params[0], expect_echo=False)
            elif command == Commands.COMMUNICATE.value:
                syncer.communicate(stdin=sys.stdin, stdout=sys.stdout)
            else:
                parser.error("Invalid command: %s" % command)
        if self.args.verbose:
            print("Total time elapsed: %.2fs" % (time.time() - started))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Copy directory structures to ESP8266')
    parser.add_argument("-v", "--verbose", dest='verbose', action="store_true", default=False,
                        help="Be verbose")
    parser.add_argument("-o", "--overwrite", dest='overwrite', action="store_true", default=False,
                        help="Overwrite (for upload/download)")
    parser.add_argument("-c", "--contents", dest='contents', action="store_true", default=False,
                        help="Copy contents of the source directory, instead of the source directory itself.")
    parser.add_argument("-q", "--quick", dest='quick', action="store_true", default=False,
                        help="Copy only if file size is different.")

    parser.add_argument("-b", "--baudrate", dest='baudrate', type=int, default=DEFAULT_BAUD_RATE,
                        help="Baud rate, default is %s" % DEFAULT_BAUD_RATE)
    parser.add_argument("-t", "--timeout", dest='timeout', type=int, default=DEFAULT_TIMEOUT,
                        help="Timeout, default is %s. Any non-positive value means infinite." % DEFAULT_TIMEOUT)
    parser.add_argument("-p", "--port", dest='port', help="Port to be used", default=None)

    parser.add_argument("--output", dest='output', default=None,
                        help="Output file. Messages received from MCU will be written here. For stdout, use '-'.")

    parser.add_argument(dest='command', default=None,
                        help="Command to be executed. Valid commands are:  " + "\n    ".join(VALID_COMMANDS) +
                             " For reading data from stdin, use execute_file -")
    parser.add_argument(dest='params', default=[], nargs='*')

    args = parser.parse_args()
    if args.port is None:
        if "ESP_PORT" in os.environ:
            args.port = os.environ["ESP_PORT"]
        else:
            parser.error("Either --port must be given or ESP_PORT environment variable must be set.")
    if args.command is None:
        parser.error("You must give a command.")

    if args.timeout <= 0:
        args.timeout = None

    Main(args).run(args.command, args.params)
