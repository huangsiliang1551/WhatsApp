"""
PID lock file to prevent multiple backend process instances.

While the process is alive, the lock holds an open file handle (write-mode)
so that if the process is killed (SIGKILL / taskkill / crash), the OS
releases the handle and subsequent instances can acquire the lock.

Usage (in main.py lifespan):
    lock = PidLock()
    lock.acquire_or_exit()
    ...
    lock.release()
"""

import logging
import os
import sys

_logger = logging.getLogger(__name__)

# fcntl is Unix-only; on Windows it will be imported lazily inside methods
_LOCK_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    ".backend.pid",
)


class PidLockError(RuntimeError):
    """Raised when the PID lock cannot be acquired."""


class PidLock:
    """File-based PID lock that prevents multiple backend instances.

    How it works:
        1. Opens/Creates .backend.pid in write mode
        2. Attempts an exclusive, non-blocking lock (fcntl.flock LOCK_EX|LOCK_NB)
        3. If another instance holds the lock → PidLockError
        4. The open file descriptor keeps the lock alive; process death releases it

    Cross-platform note:
        - fcntl is Unix-only. On Windows we fall back to a best-effort PID file.
    """

    def __init__(self, lock_path: str = _LOCK_FILE) -> None:
        self._lock_path: str = os.path.abspath(lock_path)
        self._fp: int | None = None

    def acquire_or_exit(self) -> None:
        """Try to acquire the lock.  If another instance owns it, exit the process."""
        if not self._try_acquire():
            _logger.error(f"pid_lock_held_by_another_instance lock_file={self._lock_path}")
            print(
                f"FATAL: Another backend instance holds the lock ({self._lock_path}). "
                f"Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)

    def _try_acquire(self) -> bool:
        """Return True if the lock was acquired, False if another instance holds it."""
        try:
            fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT)
        except OSError as exc:
            _logger.warning(f"pid_lock_open_failed_falling_back lock_file={self._lock_path} error={exc}")
            return True

        # On Unix: try fcntl.flock; on Windows: skip to PID file check
        if os.name != "nt":
            try:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, ImportError):
                os.close(fd)
                return False

            # Lock acquired – write our PID into the file
            self._fp = fd
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
            os.lseek(fd, 0, os.SEEK_SET)
            _logger.info(f"pid_lock_acquired pid={os.getpid()} lock_file={self._lock_path}")
            return True

        # On Windows: fall back to PID file
        os.close(fd)
        return self._try_acquire_windows()

    def _try_acquire_windows(self) -> bool:
        """Windows fallback: PID file with process-existence check."""
        if not os.path.exists(self._lock_path):
            # No lock file exists – we can claim it
            self._write_pid_file_windows()
            return True

        with open(self._lock_path, "r") as f:
            content = f.read().strip()

        if not content:
            # Stale empty file – reclaim
            self._write_pid_file_windows()
            return True

        try:
            old_pid = int(content)
        except (ValueError, TypeError):
            # Invalid content – reclaim
            self._write_pid_file_windows()
            return True

        if old_pid == os.getpid():
            # Same process – already own the lock
            return True

        if self._is_process_alive(old_pid):
            _logger.error(f"pid_lock_held_by_process existing_pid={old_pid}")
            return False

        # Process is dead – reclaim
        _logger.warning(f"pid_lock_stale_reclaimed stale_pid={old_pid}")
        self._write_pid_file_windows()
        return True

    def _write_pid_file_windows(self) -> None:
        """Write PID file (Windows fallback)."""
        try:
            with open(self._lock_path, "w") as f:
                f.write(str(os.getpid()))
        except OSError as exc:
            _logger.warning(f"pid_lock_write_failed lock_file={self._lock_path} error={exc}")

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        """Check if a process with the given PID is running (cross-platform)."""
        if os.name == "nt":
            # Windows: use tasklist to check process existence
            try:
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                return str(pid) in result.stdout
            except Exception:
                return False
        try:
            os.kill(pid, 0)  # Signal 0 = existence check (Unix)
        except OSError:
            return False
        return True

    def release(self) -> None:
        """Release the PID lock."""
        if self._fp is not None:
            try:
                os.close(self._fp)
            except OSError:
                pass
            self._fp = None

        # Remove PID file for observability
        try:
            if os.path.exists(self._lock_path):
                os.remove(self._lock_path)
        except OSError as exc:
            _logger.warning(f"pid_lock_cleanup_failed lock_file={self._lock_path} error={exc}")

        _logger.info(f"pid_lock_released pid={os.getpid()}")
