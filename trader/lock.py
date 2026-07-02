"""Single-instance lock file so two bot processes can't trade at once."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import TracebackType


class AlreadyRunningError(Exception):
    pass


class InstanceLock:
    """A simple PID-file lock. Stale locks (dead PID) are reclaimed automatically."""

    def __init__(self, path: Path):
        self.path = path
        self._acquired = False

    def acquire(self) -> None:
        if self.path.exists():
            try:
                existing_pid = int(self.path.read_text().strip())
            except (ValueError, OSError):
                existing_pid = None
            if existing_pid is not None and _pid_alive(existing_pid):
                raise AlreadyRunningError(
                    f"Another trader instance is already running (pid {existing_pid}); "
                    f"lock file: {self.path}"
                )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(str(os.getpid()))
        self._acquired = True

    def release(self) -> None:
        if self._acquired and self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass
        self._acquired = False

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
