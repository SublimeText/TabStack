from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import IO, final

import sublime

HANDSHAKE = "tabstack-keystate 1"
DEFAULT_HELPER_PATH = "/usr/local/libexec/tabstack-keystate"

_HANDSHAKE_PREFIX = "tabstack-keystate "
_SETTINGS_FILE = "TabStack.sublime-settings"
_SETTINGS_WATCH_KEY = "tab_stack_keystate_helper_path"
_PROBE_TIMEOUT_S = 2
_EXIT_TIMEOUT_S = 1


class HelperStatus(Enum):
    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"
    NO_ACCESS = "no-access"
    FAILED = "failed"


@dataclass(frozen=True)
class HelperProbe:
    # The probed path; the poller runs exactly this one, so both stay consistent
    # until the next probe even if `keystate_helper_path` changes in between.
    path: str
    status: HelperStatus
    detail: str


_probe: HelperProbe | None = None
_probe_generation = 0
# The path of the probe that is running or finished, as `_probe` may still be `None`.
_probed_path: str | None = None


def helper_path() -> str:
    path = sublime.load_settings(_SETTINGS_FILE).get("keystate_helper_path", DEFAULT_HELPER_PATH)
    if not isinstance(path, str) or not path:
        path = DEFAULT_HELPER_PATH
    return os.path.expanduser(path)


def probe_helper(path: str) -> HelperProbe:
    try:
        # Empty stdin makes the helper exit right after reporting the initial state.
        result = subprocess.run([path], input=b"", capture_output=True, timeout=_PROBE_TIMEOUT_S)
    except FileNotFoundError:
        return HelperProbe(path, HelperStatus.MISSING, f"{path} does not exist.")
    except subprocess.TimeoutExpired:
        return HelperProbe(
            path, HelperStatus.FAILED, f"{path} did not exit within {_PROBE_TIMEOUT_S} seconds."
        )
    except OSError as exc:
        return HelperProbe(path, HelperStatus.FAILED, f"{path} could not be run: {exc}")

    lines = result.stdout.decode("ascii", errors="replace").splitlines()
    return _parse_probe_output(path, lines)


def _parse_probe_output(path: str, lines: list[str]) -> HelperProbe:
    handshake = lines[0] if lines else ""
    if handshake != HANDSHAKE:
        if handshake.startswith(_HANDSHAKE_PREFIX):
            return HelperProbe(
                path,
                HelperStatus.OUTDATED,
                f"{path} speaks protocol {handshake!r}, but {HANDSHAKE!r} is required.",
            )
        return HelperProbe(
            path, HelperStatus.FAILED, f"{path} did not identify itself as `tabstack-keystate`."
        )

    report = lines[1] if len(lines) > 1 else ""
    if report in ("0", "1"):
        return HelperProbe(path, HelperStatus.OK, f"{path} reports the Ctrl key state.")
    if report.split(" ")[:2] == ["error", "no-access"]:
        return HelperProbe(
            path,
            HelperStatus.NO_ACCESS,
            f"{path} cannot open the keyboard devices: {report}",
        )
    if report.startswith("error "):
        return HelperProbe(path, HelperStatus.FAILED, f"{path} reported: {report}")
    return HelperProbe(path, HelperStatus.FAILED, f"{path} reported no Ctrl key state.")


def get_helper_probe() -> HelperProbe | None:
    """Return the result of the last probe, or `None` while it is still running."""
    return _probe


def start_helper_probe(on_done: Callable[[HelperProbe], None]) -> None:
    """Probe the helper on the async thread and call `on_done` on the main thread.

    Running the helper can take up to `_PROBE_TIMEOUT_S`, which must not block the UI.
    """
    global _probe, _probe_generation, _probed_path
    _probe = None
    _probe_generation += 1
    generation = _probe_generation
    # Resolved here because the Sublime API is only safe on the main thread.
    path = helper_path()
    _probed_path = path

    def probe() -> None:
        result = probe_helper(path)
        sublime.set_timeout(lambda: _finish_probe(generation, result, on_done))

    sublime.set_timeout_async(probe)


def _finish_probe(
    generation: int, result: HelperProbe, on_done: Callable[[HelperProbe], None]
) -> None:
    global _probe
    # A newer probe or a reset supersedes this one.
    if generation != _probe_generation:
        return
    _probe = result
    on_done(result)


def reset_helper_probe() -> None:
    global _probe, _probe_generation, _probed_path
    _probe = None
    _probe_generation += 1
    _probed_path = None


def watch_helper_path(on_change: Callable[[], None]) -> None:
    """Call `on_change` whenever `keystate_helper_path` no longer matches the probed path."""

    def on_settings_changed() -> None:
        if helper_path() != _probed_path:
            on_change()

    sublime.load_settings(_SETTINGS_FILE).add_on_change(_SETTINGS_WATCH_KEY, on_settings_changed)


@final
class HelperCtrlReleasePoller(threading.Thread):
    def __init__(self, on_release: Callable[[], None], interval_ms: int, path: str) -> None:
        super().__init__(daemon=True)
        # The helper reports state changes as they happen, so there is nothing to poll.
        _ = interval_ms
        self._on_release = on_release
        self._path = path
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        # Unknown until the helper reports the initial state, which can take longer
        # than the panel delay; assuming Ctrl held would flash the panel on a quick press.
        self._ctrl_down: bool | None = None

    def start(self) -> None:
        if self.is_alive():
            return
        super().start()

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
        self._close_stdin()

    def run(self) -> None:
        process = self._spawn()
        if process is None:
            self._fail()
            return
        try:
            if process.stdout is None:
                self._fail()
                return
            self._read_states(process.stdout)
        finally:
            self._terminate(process)

    def is_ctrl_down(self) -> bool | None:
        return self._ctrl_down

    def _spawn(self) -> subprocess.Popen[str] | None:
        with self._lock:
            if self._stop_event.is_set():
                return None
            try:
                self._process = subprocess.Popen(
                    [self._path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="ascii",
                    errors="replace",
                    bufsize=1,
                )
            except OSError as exc:
                print(f"TabStack: failed to start {self._path}: {exc}")
                return None
            return self._process

    def _read_states(self, stdout: IO[str]) -> None:
        handshake = stdout.readline().rstrip("\n")
        if handshake != HANDSHAKE:
            print(f"TabStack: unexpected handshake from {self._path}: {handshake!r}")
            self._fail()
            return

        for raw_line in iter(stdout.readline, ""):
            line = raw_line.rstrip("\n")
            if line == "1":
                self._ctrl_down = True
            elif line == "0":
                self._ctrl_down = False
                self._fire_release()
                return
            elif line.startswith("error "):
                print(f"TabStack: {self._path} reported: {line}")
                self._fail()
                return
            else:
                print(f"TabStack: unexpected line from {self._path}: {line!r}")

        self._fail()

    def _fail(self) -> None:
        self._ctrl_down = False
        self._fire_release()

    def _fire_release(self) -> None:
        # The lock makes the check-and-set atomic with respect to `stop`,
        # so that no release is scheduled once the session stopped the poller.
        with self._lock:
            if self._stop_event.is_set():
                return
            self._stop_event.set()
        sublime.set_timeout(self._on_release)

    def _close_stdin(self) -> None:
        with self._lock:
            process = self._process
            if process is None or process.stdin is None:
                return
            try:
                process.stdin.close()
            except OSError:
                pass

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        # The helper exits on stdin EOF; killing it is only the fallback.
        self._close_stdin()
        try:
            _ = process.wait(timeout=_EXIT_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            _ = process.wait()
        if process.stdout is not None:
            process.stdout.close()


def plugin_unloaded() -> None:
    sublime.load_settings(_SETTINGS_FILE).clear_on_change(_SETTINGS_WATCH_KEY)
    reset_helper_probe()
