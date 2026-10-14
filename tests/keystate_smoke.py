"""Smoke test for the `tabstack-keystate` helper against a virtual uinput keyboard.

Must run as root, with the `uinput` module loaded:

    sudo python3 -I tests/keystate_smoke.py --helper build/tabstack-keystate --user "$USER"

The user given with `--user` must not be able to read `/dev/input/event*` on its own,
otherwise the check without the capability is not meaningful.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import pwd
import selectors
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import cast

HANDSHAKE = "tabstack-keystate 1"
LINE_TIMEOUT = 2.0
SILENCE_TIMEOUT = 0.3
EXIT_TIMEOUT = 1.0
# `/tmp` is often a `nosuid` tmpfs, e.g. on systemd hosts, and the capable copy lives here.
TEMP_PARENT = "/var/tmp"

# <linux/input-event-codes.h>
EV_SYN = 0x00
EV_KEY = 0x01
SYN_REPORT = 0
KEY_LEFTCTRL = 29
KEY_A = 30
KEY_RIGHTCTRL = 97
BUS_USB = 0x03

# struct input_event: struct timeval, __u16 type, __u16 code, __s32 value
INPUT_EVENT = struct.Struct("@llHHi")
# struct uinput_setup: struct input_id (4 x __u16), char name[80], __u32 ff_effects_max
UINPUT_SETUP = struct.Struct("@HHHH80sI")


def _ioc(direction: int, number: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord("U") << 8) | number


# <linux/uinput.h>; _IOC_WRITE is 1
UI_DEV_CREATE = _ioc(0, 1, 0)
UI_DEV_DESTROY = _ioc(0, 2, 0)
UI_DEV_SETUP = _ioc(1, 3, UINPUT_SETUP.size)
UI_SET_EVBIT = _ioc(1, 100, 4)
UI_SET_KEYBIT = _ioc(1, 101, 4)


class SmokeFailure(Exception):
    pass


class VirtualKeyboard:
    def __init__(self) -> None:
        self._fd: int = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        _ = fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
        for key in (KEY_LEFTCTRL, KEY_RIGHTCTRL, KEY_A):
            _ = fcntl.ioctl(self._fd, UI_SET_KEYBIT, key)
        setup = UINPUT_SETUP.pack(BUS_USB, 0x1234, 0x5678, 1, b"tabstack-keystate smoke test", 0)
        _ = fcntl.ioctl(self._fd, UI_DEV_SETUP, setup)
        _ = fcntl.ioctl(self._fd, UI_DEV_CREATE)
        # udev needs a moment to create the device node.
        time.sleep(0.5)

    def press(self, key: int, value: int) -> None:
        _ = os.write(self._fd, INPUT_EVENT.pack(0, 0, EV_KEY, key, value))
        _ = os.write(self._fd, INPUT_EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0))

    def destroy(self) -> None:
        try:
            _ = fcntl.ioctl(self._fd, UI_DEV_DESTROY)
        finally:
            os.close(self._fd)


class Helper:
    def __init__(self, path: str, user: pwd.struct_passwd) -> None:
        command = [
            "setpriv",
            "--reuid",
            str(user.pw_uid),
            "--regid",
            str(user.pw_gid),
            "--init-groups",
            path,
        ]
        self.process: subprocess.Popen[bytes] = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        stdout = self.process.stdout
        assert stdout is not None
        self._stdout_fd: int = stdout.fileno()
        self._selector: selectors.DefaultSelector = selectors.DefaultSelector()
        _ = self._selector.register(self._stdout_fd, selectors.EVENT_READ)
        self._buffer: bytes = b""

    def read_line(self, timeout: float) -> str | None:
        """Return the next line, or `None` on timeout or EOF."""
        deadline = time.monotonic() + timeout
        while b"\n" not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._selector.select(remaining):
                return None
            chunk = os.read(self._stdout_fd, 4096)
            if not chunk:
                return None
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        return line.decode("ascii", "replace")

    def expect_line(self, expected: str, step: str) -> None:
        line = self.read_line(LINE_TIMEOUT)
        if line != expected:
            raise SmokeFailure(f"{step}: expected {expected!r}, got {line!r}")

    def expect_silence(self, step: str) -> None:
        line = self.read_line(SILENCE_TIMEOUT)
        if line is not None:
            raise SmokeFailure(f"{step}: expected no output, got {line!r}")

    def expect_exit(self, expected: int, step: str) -> None:
        try:
            status = self.process.wait(EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise SmokeFailure(f"{step}: helper still running after {EXIT_TIMEOUT} s") from None
        if status != expected:
            raise SmokeFailure(f"{step}: expected exit status {expected}, got {status}")

    def close(self) -> None:
        self._selector.close()
        if self.process.poll() is None:
            self.process.kill()
            _ = self.process.wait()
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                stream.close()


def check_capabilities_dropped(pid: int) -> None:
    with open(f"/proc/{pid}/status") as status:
        for line in status:
            name, _, value = line.partition(":")
            if name in ("CapEff", "CapPrm", "CapAmb") and int(value, 16) != 0:
                raise SmokeFailure(f"capabilities not dropped: {name} = {value.strip()}")


def run_capable(path: str, user: pwd.struct_passwd, keyboard: VirtualKeyboard) -> None:
    helper = Helper(path, user)
    try:
        helper.expect_line(HANDSHAKE, "capable: handshake")
        helper.expect_line("0", "capable: initial state")
        check_capabilities_dropped(helper.process.pid)
        for name, key in (("left", KEY_LEFTCTRL), ("right", KEY_RIGHTCTRL)):
            keyboard.press(key, 1)
            helper.expect_line("1", f"capable: {name} Ctrl down")
            keyboard.press(key, 0)
            helper.expect_line("0", f"capable: {name} Ctrl up")
        keyboard.press(KEY_A, 1)
        keyboard.press(KEY_A, 0)
        helper.expect_silence("capable: KEY_A down/up")
        stdin = helper.process.stdin
        assert stdin is not None
        stdin.close()
        helper.expect_exit(0, "capable: stdin closed")
    finally:
        helper.close()


def run_incapable(path: str, user: pwd.struct_passwd) -> None:
    helper = Helper(path, user)
    try:
        helper.expect_line(HANDSHAKE, "incapable: handshake")
        line = helper.read_line(LINE_TIMEOUT)
        if line in ("0", "1"):
            raise SmokeFailure(
                f"incapable: helper reported state {line!r} without the capability;"
                + f" user {user.pw_name!r} can already read input devices"
                + " (e.g. `input` group membership), so the negative case is not meaningful"
            )
        if line is None or not line.startswith("error no-access"):
            raise SmokeFailure(f"incapable: expected 'error no-access ...', got {line!r}")
        helper.expect_exit(1, "incapable: after error")
    finally:
        helper.close()


def check_capabilities_honored(directory: str) -> None:
    # The kernel ignores file capabilities on `nosuid` mounts (capabilities(7)).
    if os.statvfs(directory).f_flag & os.ST_NOSUID:
        raise SmokeFailure(
            f"{directory} is on a `nosuid` mount, which ignores file capabilities;"
            + f" use a temporary directory without `nosuid` (see {TEMP_PARENT})"
        )


def install_copies(helper: str, directory: str) -> tuple[str, str]:
    os.chmod(directory, 0o755)
    check_capabilities_honored(directory)
    capable = os.path.join(directory, "capable")
    incapable = os.path.join(directory, "incapable")
    for target in (capable, incapable):
        _ = shutil.copyfile(helper, target)
        os.chmod(target, 0o755)
    _ = subprocess.run(["setcap", "cap_dac_read_search=ep", capable], check=True)
    return capable, incapable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--helper", required=True, help="path to the built helper")
    _ = parser.add_argument("--user", required=True, help="unprivileged user to run it as")
    args = parser.parse_args()
    helper_path = cast(str, args.helper)
    user_name = cast(str, args.user)

    if os.geteuid() != 0:
        print("FAIL: must run as root", file=sys.stderr)
        return 1
    user = pwd.getpwnam(user_name)

    keyboard = VirtualKeyboard()
    try:
        directory = tempfile.mkdtemp(prefix="tabstack-keystate-", dir=TEMP_PARENT)
        try:
            capable, incapable = install_copies(helper_path, directory)
            run_capable(capable, user, keyboard)
            run_incapable(incapable, user)
        finally:
            shutil.rmtree(directory)
    except SmokeFailure as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    finally:
        keyboard.destroy()
    print("OK: tabstack-keystate smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
