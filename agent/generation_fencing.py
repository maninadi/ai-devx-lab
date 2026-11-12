
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypeVar

from agent.recovery_generations import sync_directory


T = TypeVar("T")
MAX_TOKEN = (1 << 63) - 1


class FencingBlocked(RuntimeError):
    pass


class GenerationFencing:
    """Local single-host filesystem fencing coordinator.

    Use a trusted pre-existing directory and a filesystem
    with reliable flock, rename, and fsync semantics.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.lock_path = self.root / "FENCE.lock"
        self.state_path = self.root / "FENCE.json"

        if not self.root.is_dir() or self.root.is_symlink():
            raise FencingBlocked("Trusted fencing root required")

    @contextmanager
    def _locked(self):
        flags = os.O_CREAT | os.O_RDWR
        flags |= getattr(os, "O_NOFOLLOW", 0)

        fd = os.open(self.lock_path, flags, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self) -> int:
        if self.state_path.is_symlink():
            raise FencingBlocked("Fencing state is a symlink")

        if not self.state_path.exists():
            return 0

        try:
            if self.state_path.stat().st_size > 128:
                raise ValueError("Oversized state")

            data = json.loads(
                self.state_path.read_text("utf-8")
            )

            if (
                not isinstance(data, dict)
                or set(data) != {"version", "token"}
                or type(data["version"]) is not int
                or data["version"] != 1
                or type(data["token"]) is not int
                or not 1 <= data["token"] <= MAX_TOKEN
            ):
                raise ValueError("Invalid state")

            return data["token"]

        except (OSError, ValueError, TypeError) as exc:
            raise FencingBlocked(
                "Fencing state unavailable or invalid"
            ) from exc

    def _write(self, token: int) -> None:
        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=".fence-",
                delete=False,
            ) as file:
                temporary = Path(file.name)
                os.chmod(temporary, 0o600)
                json.dump(
                    {"version": 1, "token": token},
                    file,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.state_path)
            temporary = None
            sync_directory(self.root)

        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def claim(self) -> int:
        """Grant new ownership, invalidating older tokens."""
        with self._locked():
            current = self._read()

            if current >= MAX_TOKEN:
                raise FencingBlocked("Token exhausted")

            token = current + 1
            self._write(token)
            return token

    def require_current(self, token: int) -> None:
        """Observation only: not a write authorization."""
        with self._locked():
            self._validate(token)

    def _validate(self, token: int) -> None:
        if type(token) is not int or token < 1:
            raise FencingBlocked("Invalid token")

        if self._read() != token:
            raise FencingBlocked("Stale fencing token")

    def guarded(self, token: int, action: Callable[[], T]) -> T:
        """Hold the lock through a protected local action."""
        with self._locked():
            self._validate(token)
            return action()
