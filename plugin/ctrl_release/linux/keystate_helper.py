from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import IO, cast, final

import sublime

HANDSHAKE = "tabstack-keystate 2"
DEFAULT_HELPER_PATH = "/usr/local/libexec/tabstack-keystate"
DEFAULT_CTRL_KEYS = ("leftctrl", "rightctrl")

_HANDSHAKE_PREFIX = "tabstack-keystate "
_SETTINGS_FILE = "TabStack.sublime-settings"
_SETTINGS_WATCH_KEY = "tab_stack_keystate_helper"
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
    # The probed path and keys; the poller runs exactly these, so both stay consistent
    # until the next probe even if the settings change in between.
    path: str
    ctrl_keys: tuple[str, ...]
    status: HelperStatus
    detail: str

    @property
    def command(self) -> list[str]:
        return [self.path, *self.ctrl_keys]


_probe: HelperProbe | None = None
_probe_generation = 0
# The path and keys of the probe that is running or finished, as `_probe` may still be `None`.
_probed_config: tuple[str, tuple[str, ...]] | None = None
# Called on the main thread once the probe result no longer holds.
_on_invalidated: Callable[[], None] | None = None


def helper_path() -> str:
    path = sublime.load_settings(_SETTINGS_FILE).get("keystate_helper_path", DEFAULT_HELPER_PATH)
    if not isinstance(path, str) or not path:
        path = DEFAULT_HELPER_PATH
    return os.path.expanduser(path)


def helper_ctrl_keys() -> tuple[str, ...]:
    keys: object = sublime.load_settings(_SETTINGS_FILE).get("keystate_ctrl_keys")
    if not isinstance(keys, list) or not keys:
        return DEFAULT_CTRL_KEYS
    # The helper validates the names against its allowlist and reports a usage error.
    return tuple(str(key) for key in cast(list[object], keys))


def _helper_config() -> tuple[str, tuple[str, ...]]:
    return helper_path(), helper_ctrl_keys()


def probe_helper(path: str, ctrl_keys: tuple[str, ...]) -> HelperProbe:
    try:
        # Empty stdin makes the helper exit right after reporting the initial state.
        result = subprocess.run(
            [path, *ctrl_keys], input=b"", capture_output=True, timeout=_PROBE_TIMEOUT_S
        )
    except FileNotFoundError:
        return HelperProbe(path, ctrl_keys, HelperStatus.MISSING, f"{path} does not exist.")
    except subprocess.TimeoutExpired:
        return HelperProbe(
            path,
            ctrl_keys,
            HelperStatus.FAILED,
            f"{path} did not exit within {_PROBE_TIMEOUT_S} seconds.",
        )
    except OSError as exc:
        return HelperProbe(path, ctrl_keys, HelperStatus.FAILED, f"{path} could not be run: {exc}")

    lines = result.stdout.decode("ascii", errors="replace").splitlines()
    return _parse_probe_output(path, ctrl_keys, lines)


def _parse_probe_output(path: str, ctrl_keys: tuple[str, ...], lines: list[str]) -> HelperProbe:
    handshake = lines[0] if lines else ""
    if handshake != HANDSHAKE:
        if handshake.startswith(_HANDSHAKE_PREFIX):
            return HelperProbe(
                path,
                ctrl_keys,
                HelperStatus.OUTDATED,
                f"{path} speaks protocol {handshake!r}, but {HANDSHAKE!r} is required.",
            )
        return HelperProbe(
            path,
            ctrl_keys,
            HelperStatus.FAILED,
            f"{path} did not identify itself as `tabstack-keystate`.",
        )

    report = lines[1] if len(lines) > 1 else ""
    if report in ("0", "1"):
        return HelperProbe(path, ctrl_keys, HelperStatus.OK, f"{path} reports the Ctrl key state.")
    if report.split(" ")[:2] == ["error", "no-access"]:
        return HelperProbe(
            path,
            ctrl_keys,
            HelperStatus.NO_ACCESS,
            f"{path} cannot open the keyboard devices: {report}",
        )
    if report.startswith("error "):
        return HelperProbe(path, ctrl_keys, HelperStatus.FAILED, f"{path} reported: {report}")
    return HelperProbe(path, ctrl_keys, HelperStatus.FAILED, f"{path} reported no Ctrl key state.")


def get_helper_probe() -> HelperProbe | None:
    """Return the result of the last probe, or `None` while it is still running."""
    return _probe


def start_helper_probe(on_done: Callable[[HelperProbe], None]) -> None:
    """Probe the helper on the async thread and call `on_done` on the main thread.

    Running the helper can take up to `_PROBE_TIMEOUT_S`, which must not block the UI.
    """
    global _probe, _probe_generation, _probed_config
    _probe = None
    _probe_generation += 1
    generation = _probe_generation
    # Resolved here because the Sublime API is only safe on the main thread.
    path, ctrl_keys = _probed_config = _helper_config()

    def probe() -> None:
        result = probe_helper(path, ctrl_keys)
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
    global _probe, _probe_generation, _probed_config
    _probe = None
    _probe_generation += 1
    _probed_config = None


def watch_helper(on_invalidated: Callable[[], None]) -> None:
    """Call `on_invalidated` whenever the probe result no longer holds.

    That is when `keystate_helper_path` or `keystate_ctrl_keys` no longer match the probe,
    or when the probed helper fails during a session.
    """
    global _on_invalidated
    _on_invalidated = on_invalidated

    def on_settings_changed() -> None:
        if _helper_config() != _probed_config:
            on_invalidated()

    sublime.load_settings(_SETTINGS_FILE).add_on_change(_SETTINGS_WATCH_KEY, on_settings_changed)


def _invalidate_probe(probe: HelperProbe) -> None:
    # A newer probe or a reset already superseded the failed one.
    if probe is not _probe or _on_invalidated is None:
        return
    _on_invalidated()


@final
class HelperCtrlReleasePoller(threading.Thread):
    def __init__(
        self, on_release: Callable[[], None], interval_ms: int, probe: HelperProbe
    ) -> None:
        super().__init__(daemon=True)
        # The helper reports state changes as they happen, so there is nothing to poll.
        _ = interval_ms
        self._on_release = on_release
        self._probe = probe
        self._path = probe.path
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
                    self._probe.command,
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
                _ = self._fire_release()
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
        if not self._fire_release():
            return
        # The helper worked when probed; probe it again so that later sessions
        # fall back to X11 or offer the setup instead of committing immediately.
        probe = self._probe
        sublime.set_timeout(lambda: _invalidate_probe(probe))

    def _fire_release(self) -> bool:
        """Schedule the release callback; return whether it was scheduled."""
        # The lock makes the check-and-set atomic with respect to `stop`,
        # so that no release is scheduled once the session stopped the poller.
        with self._lock:
            if self._stop_event.is_set():
                return False
            self._stop_event.set()
        sublime.set_timeout(self._on_release)
        return True

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
    global _on_invalidated
    sublime.load_settings(_SETTINGS_FILE).clear_on_change(_SETTINGS_WATCH_KEY)
    _on_invalidated = None
    reset_helper_probe()
